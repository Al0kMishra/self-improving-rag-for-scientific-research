import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import utcnow
from app.models import ArxivSearchCache, Paper
from app.services.arxiv_client import ArxivClient, ArxivPaper, build_search_query
from app.services.query_analysis import AnalyzedQuery, analyze_query

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    query: AnalyzedQuery
    search_query: str
    papers: list[Paper]
    from_cache: bool
    api_calls: int


def cache_key(keywords: list[str], categories: list[str], max_results: int, recency_days: int | None) -> str:
    payload = json.dumps([sorted(keywords), sorted(categories), max_results, recency_days])
    return hashlib.sha256(payload.encode()).hexdigest()


def upsert_paper(session: Session, data: ArxivPaper) -> Paper:
    paper = session.get(Paper, data.id)
    if paper is None:
        paper = Paper(id=data.id, text_status="pending")
        session.add(paper)
    elif paper.version != data.version and paper.text_status != "pending":
        paper.text_status = "pending"
        paper.pdf_error = None
        paper.indexed_model = None
        paper.chunks.clear()
    for name in (
        "version", "title", "authors", "abstract", "categories", "primary_category",
        "published_at", "updated_at", "abs_url", "pdf_url",
    ):
        setattr(paper, name, getattr(data, name))
    paper.fetched_at = utcnow()
    return paper


class PaperRetriever:
    def __init__(self, settings: Settings, client: ArxivClient | None = None):
        self.settings = settings
        self.client = client or ArxivClient(settings)

    def _cached(self, session: Session, key: str) -> list[Paper] | None:
        entry = session.get(ArxivSearchCache, key)
        if entry is None:
            return None
        if utcnow() - entry.fetched_at > timedelta(hours=self.settings.arxiv_cache_ttl_hours):
            return None
        papers = {p.id: p for p in session.scalars(select(Paper).where(Paper.id.in_(entry.paper_ids)))}
        if len(papers) != len(entry.paper_ids):
            return None
        return [papers[paper_id] for paper_id in entry.paper_ids]

    def retrieve(
        self,
        session: Session,
        text: str,
        max_results: int | None = None,
        recency_days: int | None = None,
    ) -> RetrievalResult:
        max_results = max_results or self.settings.arxiv_max_results
        recency_days = recency_days or self.settings.arxiv_recency_days
        query = analyze_query(text, self.settings.arxiv_max_keywords)
        if not query.keywords:
            raise ValueError("query has no searchable keywords")

        categories = self.settings.arxiv_categories
        key = cache_key(query.keywords, categories, max_results, recency_days)
        strict = build_search_query(query.keywords, categories, recency_days, "AND")

        cached = self._cached(session, key)
        if cached is not None:
            return RetrievalResult(query, strict, cached, from_cache=True, api_calls=0)

        search_query = strict
        result = self.client.search(search_query, max_results)
        api_calls = 1
        if len(result.papers) < self.settings.arxiv_min_results and len(query.keywords) > 1:
            search_query = build_search_query(query.keywords, categories, recency_days, "OR")
            relaxed = self.client.search(search_query, max_results)
            api_calls += 1
            seen = {p.id for p in result.papers}
            result.papers.extend(p for p in relaxed.papers if p.id not in seen)
            result.papers = result.papers[:max_results]
            logger.info("strict arXiv query returned too few results, relaxed to OR")

        papers = [upsert_paper(session, item) for item in result.papers]
        entry = session.get(ArxivSearchCache, key) or ArxivSearchCache(key=key)
        entry.search_query = search_query
        entry.paper_ids = [p.id for p in papers]
        entry.fetched_at = utcnow()
        session.merge(entry)
        session.commit()
        return RetrievalResult(query, search_query, papers, from_cache=False, api_calls=api_calls)
