from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UTCDateTime, utcnow

METRIC_FIELDS = (
    "retrieval_precision",
    "retrieval_relevance",
    "groundedness",
    "citation_accuracy",
    "answer_relevance",
    "evidence_coverage",
)


class Evaluation(Base):
    __tablename__ = "evaluations"
    __table_args__ = tuple(
        CheckConstraint(f"{name} BETWEEN 0 AND 1", name=f"ck_eval_{name}")
        for name in (*METRIC_FIELDS, "overall")
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    query_id: Mapped[int] = mapped_column(
        ForeignKey("queries.id", ondelete="CASCADE"), unique=True, index=True
    )
    retrieval_precision: Mapped[float]
    retrieval_relevance: Mapped[float]
    groundedness: Mapped[float]
    citation_accuracy: Mapped[float]
    answer_relevance: Mapped[float]
    evidence_coverage: Mapped[float]
    overall: Mapped[float]
    reasoning: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    evaluator_model: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    query: Mapped["QueryRecord"] = relationship(back_populates="evaluation")
