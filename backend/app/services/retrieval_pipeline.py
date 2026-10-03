import time
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import utcnow
from app.models import Chunk, Paper
from app.services.document_processor import DocumentProcessor, ProcessingReport
from app.services.embeddings import Embedder
from app.services.feedback_scores import feedback_scores
from app.services.indexer import Indexer
from app.services.paper_retrieval import PaperRetriever, RetrievalResult
from app.services.ranking import BASELINE_WEIGHTS, Candidate, ScoredChunk, score_candidates, select_top
from app.services.vector_store import VectorStore
from app.services.weights import RankingWeights, current_weights

Mode = Literal["baseline", "proposed"]


@dataclass
class RetrievalOutcome:
    mode: Mode
    arxiv: RetrievalResult
    processing: ProcessingReport
    query_vector: list[float]
    weights: RankingWeights
    candidates: list[ScoredChunk]
    selected: list[ScoredChunk]
    chunks: dict[str, Chunk]
    timings_ms: dict[str, float] = field(default_factory=dict)


class RetrievalPipeline:
    def __init__(
        self,
        settings: Settings,
        paper_retriever: PaperRetriever,
        document_processor: DocumentProcessor,
        indexer: Indexer,
        vector_store: VectorStore,
        embedder: Embedder,
    ):
        self.settings = settings
        self.paper_retriever = paper_retriever
        self.document_processor = document_processor
        self.indexer = indexer
        self.vector_store = vector_store
        self.embedder = embedder

    def run(
        self,
        session: Session,
        text: str,
        mode: Mode,
        max_results: int | None = None,
        recency_days: int | None = None,
        exclude_query_id: int | None = None,
        experiment_run: str | None = None,
    ) -> RetrievalOutcome:
        timings: dict[str, float] = {}

        def timed(name, func, *args, **kwargs):
            started = time.perf_counter()
            result = func(*args, **kwargs)
            timings[name] = (time.perf_counter() - started) * 1000
            return result

        arxiv = timed("arxiv", self.paper_retriever.retrieve, session, text, max_results, recency_days)
        processing = timed("processing", self.document_processor.process_papers, session, arxiv.papers)
        timed("indexing", self.indexer.index_papers, session, arxiv.papers)
        [query_vector] = timed("query_embedding", self.embedder.embed, [text])
        hits = timed(
            "vector_search",
            self.vector_store.search_vector,
            query_vector,
            self.settings.retrieval_candidate_pool,
            [paper.id for paper in arxiv.papers],
        )

        started = time.perf_counter()
        chunk_ids = [hit.chunk_id for hit in hits]
        chunks = {c.id: c for c in session.scalars(select(Chunk).where(Chunk.id.in_(chunk_ids)))}
        paper_rows = session.execute(
            select(Paper.id, Paper.published_at).where(Paper.id.in_({h.paper_id for h in hits}))
        )
        published = dict(paper_rows.tuples().all())
        candidates = [
            Candidate(hit.chunk_id, hit.paper_id, hit.similarity, published[hit.paper_id])
            for hit in hits
            if hit.chunk_id in chunks
        ]
        feedback = feedback_scores(
            session,
            [c.chunk_id for c in candidates],
            query_vector,
            self.settings.feedback_prior_strength,
            self.settings.feedback_similarity_threshold,
            exclude_query_id,
            experiment_run,
        )
        if mode == "proposed":
            weights = current_weights(session, self.settings, experiment_run)
        else:
            weights = BASELINE_WEIGHTS
        scored = score_candidates(candidates, weights, feedback, utcnow(), self.settings.recency_half_life_days)
        selected = select_top(scored, self.settings.retrieval_top_k, self.settings.max_chunks_per_paper)
        timings["ranking"] = (time.perf_counter() - started) * 1000
        timings["total"] = sum(timings.values())

        return RetrievalOutcome(
            mode=mode,
            arxiv=arxiv,
            processing=processing,
            query_vector=query_vector,
            weights=weights,
            candidates=scored,
            selected=selected,
            chunks=chunks,
            timings_ms=timings,
        )
