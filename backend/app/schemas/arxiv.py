from pydantic import BaseModel

from app.schemas.paper import PaperSummary


class ArxivSearchResponse(BaseModel):
    query: str
    keywords: list[str]
    search_query: str
    from_cache: bool
    api_calls: int
    papers: list[PaperSummary]
