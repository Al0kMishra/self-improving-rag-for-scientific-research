from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_services
from app.schemas.arxiv import ArxivSearchResponse
from app.schemas.paper import PaperSummary
from app.services.arxiv_client import ArxivError
from app.services.container import Services

router = APIRouter(prefix="/arxiv", tags=["arxiv"])


@router.get("/search", response_model=ArxivSearchResponse)
def search_arxiv(
    q: str = Query(..., min_length=3, max_length=500),
    max_results: int | None = Query(None, ge=1, le=100),
    recency_days: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    services: Services = Depends(get_services),
) -> ArxivSearchResponse:
    try:
        result = services.paper_retriever.retrieve(db, q, max_results, recency_days)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ArxivError as exc:
        raise HTTPException(status_code=502, detail=f"arXiv unavailable: {exc}") from exc
    return ArxivSearchResponse(
        query=result.query.original,
        keywords=result.query.keywords,
        search_query=result.search_query,
        from_cache=result.from_cache,
        api_calls=result.api_calls,
        papers=[PaperSummary.model_validate(p) for p in result.papers],
    )
