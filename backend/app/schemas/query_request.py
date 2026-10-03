from typing import Literal

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    mode: Literal["baseline", "proposed"] = "proposed"
    experiment_run: str | None = Field(None, max_length=64)
    cycle: int | None = Field(None, ge=0)
    max_results: int | None = Field(None, ge=1, le=100)
    recency_days: int | None = Field(None, ge=1)
    learn: bool = True
