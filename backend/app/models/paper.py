from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UTCDateTime, utcnow

TEXT_STATUSES = ("pending", "extracted", "abstract_only", "failed")
CHUNK_SOURCES = ("pdf", "abstract")


class Paper(Base):
    __tablename__ = "papers"
    __table_args__ = (
        CheckConstraint(f"text_status IN {TEXT_STATUSES}", name="ck_paper_text_status"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    version: Mapped[str | None] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[list[str]] = mapped_column(JSON, default=list)
    abstract: Mapped[str] = mapped_column(Text)
    categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    primary_category: Mapped[str | None] = mapped_column(String(32))
    published_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    abs_url: Mapped[str] = mapped_column(String(256))
    pdf_url: Mapped[str | None] = mapped_column(String(256))
    text_status: Mapped[str] = mapped_column(String(16), default="pending")
    pdf_error: Mapped[str | None] = mapped_column(Text)
    indexed_model: Mapped[str | None] = mapped_column(String(128))
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", order_by="Chunk.chunk_index"
    )


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("paper_id", "chunk_index", name="uq_chunk_position"),
        CheckConstraint(f"source IN {CHUNK_SOURCES}", name="ck_chunk_source"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int]
    section: Mapped[str | None] = mapped_column(String(256))
    page: Mapped[int | None]
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16))

    paper: Mapped[Paper] = relationship(back_populates="chunks")

    @staticmethod
    def make_id(paper_id: str, chunk_index: int) -> str:
        return f"{paper_id}#{chunk_index}"
