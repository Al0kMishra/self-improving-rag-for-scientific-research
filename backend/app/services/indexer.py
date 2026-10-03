from sqlalchemy.orm import Session

from app.models import Paper
from app.services.vector_store import VectorStore


class Indexer:
    def __init__(self, store: VectorStore):
        self.store = store

    @property
    def model_name(self) -> str:
        return self.store.embedder.model_name

    def needs_indexing(self, paper: Paper) -> bool:
        return paper.indexed_model != self.model_name and paper.text_status != "pending"

    def index_papers(self, session: Session, papers: list[Paper]) -> list[str]:
        indexed = []
        for paper in papers:
            if not self.needs_indexing(paper):
                continue
            self.store.index_paper(paper)
            paper.indexed_model = self.model_name
            indexed.append(paper.id)
        session.commit()
        return indexed
