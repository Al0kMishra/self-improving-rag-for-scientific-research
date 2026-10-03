import logging
import time
from typing import Literal

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Citation, QueryRecord, RetrievedChunk
from app.services.adaptation import WeightAdapter
from app.services.citations import map_citations
from app.services.evaluation import SelfEvaluator
from app.services.generation import AnswerGenerator, EvidenceItem
from app.services.retrieval_pipeline import RetrievalOutcome, RetrievalPipeline

logger = logging.getLogger(__name__)

Mode = Literal["baseline", "proposed"]


def build_evidence(outcome: RetrievalOutcome) -> list[EvidenceItem]:
    evidence = []
    for number, item in enumerate(outcome.selected, start=1):
        chunk = outcome.chunks[item.chunk_id]
        evidence.append(
            EvidenceItem(
                number=number,
                chunk_id=chunk.id,
                paper_id=chunk.paper_id,
                title=chunk.paper.title,
                year=chunk.paper.published_at.year,
                section=chunk.section,
                page=chunk.page,
                text=chunk.text,
            )
        )
    return evidence


class QueryPipeline:
    def __init__(
        self,
        settings: Settings,
        retrieval: RetrievalPipeline,
        generator: AnswerGenerator,
        evaluator: SelfEvaluator | None = None,
        adapter: WeightAdapter | None = None,
    ):
        self.settings = settings
        self.retrieval = retrieval
        self.generator = generator
        self.evaluator = evaluator
        self.adapter = adapter

    def _store_retrieval(self, record: QueryRecord, outcome: RetrievalOutcome) -> None:
        record.keywords = outcome.arxiv.query.keywords
        record.search_query = outcome.arxiv.search_query
        record.embedding = outcome.query_vector
        record.alpha, record.beta, record.gamma = outcome.weights.alpha, outcome.weights.beta, outcome.weights.gamma
        record.retrieval_ms = outcome.timings_ms["total"]
        record.retrieved = [
            RetrievedChunk(
                chunk_id=item.chunk_id,
                rank=rank,
                similarity=item.similarity,
                semantic_score=item.semantic,
                recency_score=item.recency,
                feedback_score=item.feedback,
                final_score=item.final,
            )
            for rank, item in enumerate(outcome.selected, start=1)
        ]

    def _generate(self, record: QueryRecord, evidence: list[EvidenceItem]) -> None:
        started = time.perf_counter()
        generated = self.generator.generate(record.text, evidence)
        record.generation_ms = (time.perf_counter() - started) * 1000
        mapped = map_citations(generated.answer, len(evidence))
        record.answer = mapped.answer
        record.insufficient_evidence = generated.insufficient_evidence
        record.missing_information = generated.missing_information
        record.invalid_citations = mapped.invalid_markers
        record.total_claims = len(mapped.claims)
        record.uncited_claims = len(mapped.uncited_claims)
        record.llm_model = self.generator.model
        by_number = {item.number: item for item in evidence}
        record.citations = [
            Citation(
                marker=link.marker,
                claim_index=link.claim_index,
                chunk_id=by_number[link.marker].chunk_id,
                claim=link.claim,
            )
            for link in mapped.links
        ]

    def run(
        self,
        session: Session,
        text: str,
        mode: Mode,
        experiment_run: str | None = None,
        cycle: int | None = None,
        max_results: int | None = None,
        recency_days: int | None = None,
        learn: bool = True,
        phase: str | None = None,
    ) -> QueryRecord:
        started = time.perf_counter()
        record = QueryRecord(
            text=text.strip(),
            mode=mode,
            status="pending",
            alpha=0.0,
            beta=0.0,
            gamma=0.0,
            experiment_run=experiment_run,
            cycle=cycle,
            phase=phase,
        )
        session.add(record)
        session.commit()
        try:
            outcome = self.retrieval.run(
                session, record.text, mode, max_results, recency_days,
                exclude_query_id=record.id, experiment_run=experiment_run,
            )
            self._store_retrieval(record, outcome)
            evidence = build_evidence(outcome)
            self._generate(record, evidence)
            record.status = "completed"
            record.total_ms = (time.perf_counter() - started) * 1000
            session.commit()
            if self.evaluator is not None:
                self.evaluator(session, record, evidence)
            if learn and self.adapter is not None:
                self.adapter.update(session, record, "evaluation")
            record.total_ms = (time.perf_counter() - started) * 1000
            session.commit()
        except Exception as exc:
            session.rollback()
            record = session.get(QueryRecord, record.id)
            record.status = "failed"
            record.error = f"{type(exc).__name__}: {exc}"[:2000]
            record.total_ms = (time.perf_counter() - started) * 1000
            session.commit()
            logger.exception("query %s failed", record.id)
        return record
