from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FeedbackCreate(BaseModel):
    query_id: int
    rating: Literal[-1, 1]
    chunk_id: str | None = None
    comment: str | None = Field(None, max_length=2000)


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    query_id: int
    rating: int
    chunk_id: str | None
    comment: str | None
    created_at: datetime
