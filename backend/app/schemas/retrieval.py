from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.paper import PaperSummary
from app.schemas.weights import Weights


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    mode: Literal["baseline", "proposed"] = "proposed"
    max_results: int | None = Field(None, ge=1, le=100)
    recency_days: int | None = Field(None, ge=1)


class RankedChunkOut(BaseModel):
    rank: int
    chunk_id: str
    paper: PaperSummary
    section: str | None
    page: int | None
    source: str
    text: str
    similarity: float
    semantic_score: float
    recency_score: float
    feedback_score: float
    final_score: float


class RetrieveResponse(BaseModel):
    query: str
    mode: str
    keywords: list[str]
    search_query: str
    from_cache: bool
    papers_found: int
    full_text_papers: list[str]
    weights: Weights
    candidates_considered: int
    results: list[RankedChunkOut]
    timings_ms: dict[str, float]
