from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_services
from app.models import QueryRecord
from app.schemas.feedback import FeedbackOut
from app.schemas.paper import PaperSummary
from app.schemas.query import (
    CitationOut,
    EvaluationOut,
    Latency,
    QueryDetail,
    RetrievedChunkOut,
)
from app.schemas.query_request import QueryRequest
from app.schemas.weights import Weights
from app.services.container import Services

router = APIRouter(prefix="/query", tags=["query"])


def build_query_detail(record: QueryRecord) -> QueryDetail:
    cited_ids = {citation.chunk_id for citation in record.citations}
    return QueryDetail(
        id=record.id,
        text=record.text,
        reformulated_text=record.reformulated_text,
        mode=record.mode,
        status=record.status,
        answer=record.answer,
        insufficient_evidence=record.insufficient_evidence,
        missing_information=record.missing_information,
        invalid_citations=record.invalid_citations or [],
        total_claims=record.total_claims,
        uncited_claims=record.uncited_claims,
        keywords=record.keywords or [],
        search_query=record.search_query,
        llm_model=record.llm_model,
        error=record.error,
        weights=Weights(alpha=record.alpha, beta=record.beta, gamma=record.gamma),
        latency=Latency(
            retrieval_ms=record.retrieval_ms,
            generation_ms=record.generation_ms,
            evaluation_ms=record.evaluation_ms,
            total_ms=record.total_ms,
        ),
        experiment_run=record.experiment_run,
        cycle=record.cycle,
        phase=record.phase,
        created_at=record.created_at,
        retrieved=[
            RetrievedChunkOut(
                rank=item.rank,
                chunk_id=item.chunk_id,
                paper=PaperSummary.model_validate(item.chunk.paper),
                section=item.chunk.section,
                page=item.chunk.page,
                source=item.chunk.source,
                text=item.chunk.text,
                semantic_score=item.semantic_score,
                recency_score=item.recency_score,
                feedback_score=item.feedback_score,
                final_score=item.final_score,
                similarity=item.similarity,
                judged_relevance=item.judged_relevance,
                cited=item.chunk_id in cited_ids,
            )
            for item in record.retrieved
        ],
        citations=[
            CitationOut(
                marker=citation.marker,
                claim_index=citation.claim_index,
                chunk_id=citation.chunk_id,
                paper_id=citation.chunk.paper_id,
                paper_title=citation.chunk.paper.title,
                claim=citation.claim,
                support=citation.support,
                verdict_reason=citation.verdict_reason,
            )
            for citation in record.citations
        ],
        evaluation=EvaluationOut.model_validate(record.evaluation) if record.evaluation else None,
        feedback=[FeedbackOut.model_validate(item) for item in record.feedback],
    )


@router.post("", response_model=QueryDetail)
def run_query(
    payload: QueryRequest,
    db: Session = Depends(get_db),
    services: Services = Depends(get_services),
):
    if services.query_pipeline is None:
        raise HTTPException(status_code=503, detail="LLM is not configured, set LLM_API_KEY or LLM_BASE_URL")
    record = services.query_pipeline.run(
        db, payload.query, payload.mode, payload.experiment_run, payload.cycle,
        payload.max_results, payload.recency_days, payload.learn,
    )
    detail = build_query_detail(record)
    if record.status == "failed":
        return JSONResponse(status_code=502, content=detail.model_dump(mode="json"))
    return detail


@router.get("", response_model=list[QueryDetail])
def list_queries(
    limit: int = 20,
    experiment_run: str | None = None,
    db: Session = Depends(get_db),
) -> list[QueryDetail]:
    stmt = select(QueryRecord).order_by(QueryRecord.id.desc()).limit(min(limit, 200))
    if experiment_run is not None:
        stmt = stmt.where(QueryRecord.experiment_run == experiment_run)
    return [build_query_detail(record) for record in db.scalars(stmt)]


@router.get("/{query_id}", response_model=QueryDetail)
def get_query(query_id: int, db: Session = Depends(get_db)) -> QueryDetail:
    record = db.get(QueryRecord, query_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"query {query_id} not found")
    return build_query_detail(record)
