from datetime import datetime, timedelta, timezone

import pytest

from app.models import Feedback, QueryRecord, RetrievedChunk
from app.services.feedback_scores import feedback_scores, similarity_kernel
from app.services.paper_retrieval import PaperRetriever
from app.services.ranking import (
    Candidate,
    ScoredChunk,
    min_max,
    recency_score,
    score_candidates,
    select_top,
)
from app.services.weights import RankingWeights
from tests.factories import make_paper, make_query
from tests.fakes import FakeArxivClient, HashEmbedder, arxiv_paper

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_recency_halves_every_half_life():
    assert recency_score(NOW, NOW, 365) == 1.0
    assert recency_score(NOW - timedelta(days=365), NOW, 365) == pytest.approx(0.5)
    assert recency_score(NOW - timedelta(days=730), NOW, 365) == pytest.approx(0.25)
    assert recency_score(NOW + timedelta(days=3), NOW, 365) == 1.0


def test_min_max():
    assert min_max([0.2, 0.4, 0.6]) == pytest.approx([0.0, 0.5, 1.0])
    assert min_max([0.3, 0.3]) == [1.0, 1.0]
    assert min_max([]) == []


def test_weights_change_the_order():
    old_relevant = Candidate("old#0", "old", 0.80, NOW - timedelta(days=2000))
    new_related = Candidate("new#0", "new", 0.70, NOW)
    semantic_only = score_candidates([old_relevant, new_related], RankingWeights(1, 0, 0), {}, NOW, 365)
    recency_heavy = score_candidates([old_relevant, new_related], RankingWeights(0.4, 0.6, 0), {}, NOW, 365)
    assert select_top(semantic_only, 2, 3)[0].chunk_id == "old#0"
    assert select_top(recency_heavy, 2, 3)[0].chunk_id == "new#0"


def test_final_score_is_weighted_sum():
    [scored] = score_candidates(
        [Candidate("a#0", "a", 0.5, NOW - timedelta(days=365))],
        RankingWeights(0.6, 0.2, 0.2),
        {"a#0": 0.9},
        NOW,
        365,
    )
    assert scored.final == pytest.approx(0.6 * 1.0 + 0.2 * 0.5 + 0.2 * 0.9)


def test_select_top_caps_chunks_per_paper():
    scored = [ScoredChunk(f"a#{i}", "a", 0.9, 1, 1, 0.5, 1 - i / 10) for i in range(4)]
    scored.append(ScoredChunk("b#0", "b", 0.5, 0, 0, 0.5, 0.1))
    assert [s.chunk_id for s in select_top(scored, 4, 2)] == ["a#0", "a#1", "b#0"]


def test_similarity_kernel():
    assert similarity_kernel(1.0, 0.3) == 1.0
    assert similarity_kernel(0.3, 0.3) == 0.0
    assert similarity_kernel(0.65, 0.3) == pytest.approx(0.5)


def store_query(db, embedding, chunk_id, relevance=None):
    record = QueryRecord(text="q", mode="proposed", status="completed", alpha=0.7, beta=0.15, gamma=0.15,
                         embedding=embedding)
    record.retrieved = [RetrievedChunk(chunk_id=chunk_id, rank=1, similarity=0.5, semantic_score=1,
                                       recency_score=1, feedback_score=0.5, final_score=1,
                                       judged_relevance=relevance)]
    db.add(record)
    db.commit()
    return record


def test_feedback_scores_follow_signals_from_similar_queries(db):
    make_paper(db, "2501.00001", ("good chunk", "bad chunk", "unseen chunk"))
    same = [1.0, 0.0]
    unrelated = [0.0, 1.0]
    liked = store_query(db, same, "2501.00001#0", relevance=1.0)
    db.add(Feedback(query_id=liked.id, chunk_id="2501.00001#0", rating=1))
    disliked = store_query(db, same, "2501.00001#1", relevance=0.0)
    db.add(Feedback(query_id=disliked.id, chunk_id="2501.00001#1", rating=-1))
    elsewhere = store_query(db, unrelated, "2501.00001#2", relevance=0.0)
    db.add(Feedback(query_id=elsewhere.id, chunk_id="2501.00001#2", rating=-1))
    db.commit()

    ids = ["2501.00001#0", "2501.00001#1", "2501.00001#2"]
    scores = feedback_scores(db, ids, same, prior_strength=2.0, similarity_threshold=0.3)
    assert scores["2501.00001#0"] == pytest.approx((1 + 1.5) / (2 + 1.5))
    assert scores["2501.00001#1"] == pytest.approx(1 / (2 + 1.5))
    assert scores["2501.00001#2"] == 0.5

    excluded = feedback_scores(db, ids, same, 2.0, 0.3, exclude_query_id=liked.id)
    assert excluded["2501.00001#0"] == 0.5


def test_answer_level_feedback_reaches_cited_chunks(db):
    paper = make_paper(db, "2501.00001", ("cited", "not cited"))
    record = make_query(db, paper, cited=(0,))
    record.embedding = [1.0, 0.0]
    db.add(Feedback(query_id=record.id, rating=-1))
    db.commit()
    scores = feedback_scores(db, ["2501.00001#0", "2501.00001#1"], [1.0, 0.0], 2.0, 0.3)
    assert scores["2501.00001#0"] < 0.5
    assert scores["2501.00001#1"] == 0.5


@pytest.fixture
def corpus(settings, services):
    papers = [
        arxiv_paper("2001.00001", "Speculative decoding for language models",
                    "Speculative decoding uses a draft model to propose tokens for faster inference.",
                    NOW - timedelta(days=900)),
        arxiv_paper("2601.00002", "Faster speculative decoding with tree drafts",
                    "Tree based drafts speed up speculative decoding of language models.",
                    NOW - timedelta(days=30)),
        arxiv_paper("2401.00003", "Graph neural network expressivity",
                    "Message passing graph networks are bounded by the WL test.",
                    NOW - timedelta(days=400)),
    ]
    services.retrieval.paper_retriever = PaperRetriever(settings, FakeArxivClient(papers))
    return services


def test_retrieval_pipeline_end_to_end(corpus, db):
    outcome = corpus.retrieval.run(db, "speculative decoding language models", "proposed")
    assert outcome.processing.abstract_only == ["2001.00001", "2601.00002", "2401.00003"]
    assert len(outcome.selected) == 3
    assert {s.paper_id for s in outcome.selected[:2]} == {"2001.00001", "2601.00002"}
    assert outcome.weights == RankingWeights(0.7, 0.15, 0.15)
    assert set(outcome.timings_ms) >= {"arxiv", "processing", "indexing", "vector_search", "ranking", "total"}
    assert len(outcome.query_vector) == HashEmbedder.dimensions


def test_baseline_ignores_recency_and_feedback(corpus, db):
    outcome = corpus.retrieval.run(db, "speculative decoding language models", "baseline")
    assert outcome.weights == RankingWeights(1.0, 0.0, 0.0)
    assert all(s.final == s.semantic for s in outcome.selected)
    assert [s.similarity for s in outcome.selected] == sorted((s.similarity for s in outcome.selected), reverse=True)


def test_retrieve_endpoint(client, corpus):
    body = client.post("/api/retrieve", json={"query": "speculative decoding language models"}).json()
    assert body["mode"] == "proposed"
    assert body["papers_found"] == 3
    first = body["results"][0]
    assert set(first) >= {"similarity", "semantic_score", "recency_score", "feedback_score", "final_score"}
    assert first["final_score"] == pytest.approx(
        0.7 * first["semantic_score"] + 0.15 * first["recency_score"] + 0.15 * first["feedback_score"]
    )
    assert client.post("/api/retrieve", json={"query": "the a of"}).status_code == 422
