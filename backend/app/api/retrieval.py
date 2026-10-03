from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_services
from app.schemas.paper import PaperSummary
from app.schemas.retrieval import RankedChunkOut, RetrieveRequest, RetrieveResponse
from app.schemas.weights import Weights
from app.services.arxiv_client import ArxivError
from app.services.container import Services
from app.services.retrieval_pipeline import RetrievalOutcome

router = APIRouter(prefix="/retrieve", tags=["retrieval"])


def ranked_chunks(outcome: RetrievalOutcome) -> list[RankedChunkOut]:
    results = []
    for rank, item in enumerate(outcome.selected, start=1):
        chunk = outcome.chunks[item.chunk_id]
        results.append(
            RankedChunkOut(
                rank=rank,
                chunk_id=item.chunk_id,
                paper=PaperSummary.model_validate(chunk.paper),
                section=chunk.section,
                page=chunk.page,
                source=chunk.source,
                text=chunk.text,
                similarity=item.similarity,
                semantic_score=item.semantic,
                recency_score=item.recency,
                feedback_score=item.feedback,
                final_score=item.final,
            )
        )
    return results


@router.post("", response_model=RetrieveResponse)
def retrieve(
    payload: RetrieveRequest,
    db: Session = Depends(get_db),
    services: Services = Depends(get_services),
) -> RetrieveResponse:
    try:
        outcome = services.retrieval.run(db, payload.query, payload.mode, payload.max_results, payload.recency_days)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ArxivError as exc:
        raise HTTPException(status_code=502, detail=f"arXiv unavailable: {exc}") from exc
    weights = outcome.weights
    return RetrieveResponse(
        query=payload.query,
        mode=payload.mode,
        keywords=outcome.arxiv.query.keywords,
        search_query=outcome.arxiv.search_query,
        from_cache=outcome.arxiv.from_cache,
        papers_found=len(outcome.arxiv.papers),
        full_text_papers=[p.id for p in outcome.arxiv.papers if p.text_status == "extracted"],
        weights=Weights(alpha=weights.alpha, beta=weights.beta, gamma=weights.gamma),
        candidates_considered=len(outcome.candidates),
        results=ranked_chunks(outcome),
        timings_ms=outcome.timings_ms,
    )
