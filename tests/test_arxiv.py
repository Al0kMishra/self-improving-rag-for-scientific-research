from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import ArxivSearchCache, Paper
from app.services.arxiv_client import (
    ArxivClient,
    ArxivError,
    ArxivPaper,
    ArxivSearchResult,
    build_search_query,
    parse_feed,
    split_arxiv_id,
)
from app.services.paper_retrieval import PaperRetriever
from app.services.query_analysis import extract_keywords

FEED = (Path(__file__).parent / "fixtures" / "arxiv_feed.xml").read_text()


def paper(paper_id, version="v1"):
    return ArxivPaper(
        id=paper_id,
        version=version,
        title=f"Title {paper_id}",
        authors=["X"],
        abstract="Abstract",
        categories=["cs.LG"],
        primary_category="cs.LG",
        published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated_at=None,
        abs_url=f"https://arxiv.org/abs/{paper_id}",
        pdf_url=f"https://arxiv.org/pdf/{paper_id}{version}",
    )


class FakeClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.queries = []

    def search(self, search_query, max_results):
        self.queries.append(search_query)
        return ArxivSearchResult(total_results=0, papers=list(self.responses.pop(0)))


@pytest.fixture
def fast_settings(settings):
    return settings.model_copy(update={"arxiv_min_results": 2})


def test_parse_feed():
    result = parse_feed(FEED)
    assert result.total_results == 2634
    first, old = result.papers
    assert (first.id, first.version) == ("2507.23334", "v2")
    assert first.title == "MUST-RAG: MUSical Text Question Answering with Retrieval Augmented Generation"
    assert first.authors == ["Daeyong Kwon", "Juhan Nam"]
    assert first.categories == ["cs.CL", "cs.AI"]
    assert first.primary_category == "cs.CL"
    assert first.pdf_url == "https://arxiv.org/pdf/2507.23334v2"
    assert first.published_at == datetime(2025, 7, 31, 8, 31, 5, tzinfo=timezone.utc)
    assert (old.id, old.version, old.pdf_url) == ("cs/0112017", "v1", None)


def test_parse_feed_rejects_garbage():
    with pytest.raises(ArxivError):
        parse_feed("<not xml")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://arxiv.org/abs/2401.12345v3", ("2401.12345", "v3")),
        ("http://arxiv.org/abs/cs/0112017v1", ("cs/0112017", "v1")),
        ("http://arxiv.org/abs/2401.12345", ("2401.12345", None)),
    ],
)
def test_split_arxiv_id(raw, expected):
    assert split_arxiv_id(raw) == expected


def test_extract_keywords_drops_question_words():
    keywords = extract_keywords("How does chain-of-thought prompting affect LLM reasoning?", 5)
    assert keywords == ["chain-of-thought", "prompting", "llm", "reasoning"]
    assert extract_keywords("a b c the of", 5) == []


def test_build_search_query():
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    query = build_search_query(["chain-of-thought", "llm"], ["cs.AI", "cs.CL"], 30, now=now)
    assert query == (
        '(all:"chain of thought" AND all:llm) AND (cat:cs.AI OR cat:cs.CL) '
        "AND submittedDate:[202609021200 TO 202610021200]"
    )
    assert "submittedDate" not in build_search_query(["llm"], ["cs.AI"], None, "OR")


def test_client_retries_then_succeeds(fast_settings):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, text=FEED)

    client = ArxivClient(fast_settings, httpx.Client(transport=httpx.MockTransport(handler)))
    assert len(client.search("all:rag", 5).papers) == 2
    assert len(calls) == 2
    assert calls[1].url.params["max_results"] == "5"


def test_client_honours_retry_after(fast_settings, monkeypatch):
    waits = []
    monkeypatch.setattr("app.services.arxiv_client.time.sleep", waits.append)
    responses = iter([httpx.Response(429, headers={"retry-after": "7"}), httpx.Response(200, text=FEED)])
    client = ArxivClient(fast_settings, httpx.Client(transport=httpx.MockTransport(lambda r: next(responses))))
    client.search("all:rag", 5)
    assert 7.0 in waits


def test_client_gives_up_on_client_error(fast_settings):
    client = ArxivClient(fast_settings, httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(400))))
    with pytest.raises(ArxivError):
        client.search("all:rag", 5)


def test_retriever_caches_results(client, db, fast_settings):
    fake = FakeClient([paper("2501.00001"), paper("2501.00002")])
    retriever = PaperRetriever(fast_settings, fake)
    first = retriever.retrieve(db, "sparse attention transformers")
    second = retriever.retrieve(db, "transformers with sparse attention")
    assert (first.from_cache, first.api_calls) == (False, 1)
    assert (second.from_cache, second.api_calls) == (True, 0)
    assert [p.id for p in second.papers] == ["2501.00001", "2501.00002"]
    assert len(fake.queries) == 1


def test_retriever_relaxes_to_or_when_too_few(client, db, fast_settings):
    fake = FakeClient([paper("2501.00001")], [paper("2501.00001"), paper("2501.00003")])
    result = PaperRetriever(fast_settings, fake).retrieve(db, "mamba state space models")
    assert " AND all:" in fake.queries[0] and " OR all:" in fake.queries[1]
    assert [p.id for p in result.papers] == ["2501.00001", "2501.00003"]
    assert result.api_calls == 2


def test_retriever_resets_text_on_new_version(client, db, fast_settings):
    PaperRetriever(fast_settings, FakeClient([paper("2501.00001"), paper("2501.00002")])).retrieve(db, "diffusion")
    stored = db.get(Paper, "2501.00001")
    stored.text_status = "extracted"
    db.query(ArxivSearchCache).delete()
    db.commit()
    PaperRetriever(fast_settings, FakeClient([paper("2501.00001", "v2"), paper("2501.00002")])).retrieve(
        db, "diffusion"
    )
    db.refresh(stored)
    assert (stored.version, stored.text_status) == ("v2", "pending")


def test_search_endpoint(fast_settings, services):
    services.paper_retriever = PaperRetriever(fast_settings, FakeClient([paper("2501.00001"), paper("2501.00002")]))
    with TestClient(create_app(fast_settings, services)) as client:
        body = client.get("/api/arxiv/search", params={"q": "graph neural networks"}).json()
        assert body["keywords"] == ["graph", "neural", "networks"]
        assert body["papers"][0]["id"] == "2501.00001"
        assert client.get("/api/arxiv/search", params={"q": "what is the"}).status_code == 422


def test_keywords_keep_domain_terms():
    assert extract_keywords("How do state space models compare to transformers?", 5) == [
        "state", "space", "models", "transformers",
    ]
