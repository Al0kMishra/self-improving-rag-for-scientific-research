from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UTCDateTime, utcnow

TRIGGERS = ("init", "evaluation", "feedback", "manual")


class WeightSnapshot(Base):
    __tablename__ = "weight_snapshots"
    __table_args__ = (CheckConstraint(f"trigger IN {TRIGGERS}", name="ck_weight_trigger"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    alpha: Mapped[float]
    beta: Mapped[float]
    gamma: Mapped[float]
    trigger: Mapped[str] = mapped_column(String(16))
    experiment_run: Mapped[str | None] = mapped_column(String(64), index=True)
    query_id: Mapped[int | None] = mapped_column(ForeignKey("queries.id", ondelete="SET NULL"))
    signal: Mapped[float | None]
    note: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
