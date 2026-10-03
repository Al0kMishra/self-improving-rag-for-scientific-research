from datetime import datetime

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UTCDateTime, utcnow


class ArxivSearchCache(Base):
    __tablename__ = "arxiv_search_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    search_query: Mapped[str] = mapped_column(Text)
    paper_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
