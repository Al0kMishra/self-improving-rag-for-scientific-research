from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UTCDateTime, utcnow
from app.models.paper import Chunk

MODES = ("baseline", "proposed")
QUERY_STATUSES = ("pending", "completed", "failed")


class QueryRecord(Base):
    __tablename__ = "queries"
    __table_args__ = (
        CheckConstraint(f"mode IN {MODES}", name="ck_query_mode"),
        CheckConstraint(f"status IN {QUERY_STATUSES}", name="ck_query_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    reformulated_text: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    search_query: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(JSON)
    mode: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    answer: Mapped[str | None] = mapped_column(Text)
    insufficient_evidence: Mapped[bool] = mapped_column(default=False)
    missing_information: Mapped[str | None] = mapped_column(Text)
    invalid_citations: Mapped[list[int]] = mapped_column(JSON, default=list)
    uncited_claims: Mapped[int] = mapped_column(default=0)
    total_claims: Mapped[int] = mapped_column(default=0)
    llm_model: Mapped[str | None] = mapped_column(String(128))
    error: Mapped[str | None] = mapped_column(Text)

    alpha: Mapped[float]
    beta: Mapped[float]
    gamma: Mapped[float]

    retrieval_ms: Mapped[float | None]
    generation_ms: Mapped[float | None]
    evaluation_ms: Mapped[float | None]
    total_ms: Mapped[float | None]

    experiment_run: Mapped[str | None] = mapped_column(String(64), index=True)
    cycle: Mapped[int | None]
    phase: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)

    retrieved: Mapped[list["RetrievedChunk"]] = relationship(
        back_populates="query", cascade="all, delete-orphan", order_by="RetrievedChunk.rank"
    )
    citations: Mapped[list["Citation"]] = relationship(
        back_populates="query", cascade="all, delete-orphan", order_by=lambda: [Citation.claim_index, Citation.marker]
    )
    evaluation: Mapped["Evaluation | None"] = relationship(
        back_populates="query", cascade="all, delete-orphan", uselist=False
    )
    feedback: Mapped[list["Feedback"]] = relationship(
        back_populates="query", cascade="all, delete-orphan", order_by="Feedback.id"
    )


class RetrievedChunk(Base):
    __tablename__ = "retrieved_chunks"
    __table_args__ = (UniqueConstraint("query_id", "chunk_id", name="uq_retrieved_chunk"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    query_id: Mapped[int] = mapped_column(ForeignKey("queries.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id"), index=True)
    rank: Mapped[int]
    similarity: Mapped[float]
    semantic_score: Mapped[float]
    recency_score: Mapped[float]
    feedback_score: Mapped[float]
    final_score: Mapped[float]
    judged_relevance: Mapped[float | None]

    query: Mapped[QueryRecord] = relationship(back_populates="retrieved")
    chunk: Mapped[Chunk] = relationship()


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    query_id: Mapped[int] = mapped_column(ForeignKey("queries.id", ondelete="CASCADE"), index=True)
    marker: Mapped[int]
    claim_index: Mapped[int] = mapped_column(default=0)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id"))
    claim: Mapped[str | None] = mapped_column(Text)
    support: Mapped[float | None]
    verdict_reason: Mapped[str | None] = mapped_column(Text)

    query: Mapped[QueryRecord] = relationship(back_populates="citations")
    chunk: Mapped[Chunk] = relationship()
