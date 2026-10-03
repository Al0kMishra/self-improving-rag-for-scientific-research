from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PaperSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    authors: list[str]
    primary_category: str | None
    published_at: datetime
    abs_url: str
    pdf_url: str | None


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chunk_index: int
    section: str | None
    page: int | None
    source: str
    text: str


class PaperDetail(PaperSummary):
    version: str | None
    abstract: str
    categories: list[str]
    updated_at: datetime | None
    text_status: str
    pdf_error: str | None
    fetched_at: datetime
    chunk_count: int
    chunks: list[ChunkOut] | None = None
