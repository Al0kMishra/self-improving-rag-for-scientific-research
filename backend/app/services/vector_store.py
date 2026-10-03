from dataclasses import dataclass

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import Settings
from app.models import Chunk, Paper
from app.services.embeddings import Embedder


@dataclass
class VectorHit:
    chunk_id: str
    paper_id: str
    similarity: float


def embedding_text(paper: Paper, chunk: Chunk) -> str:
    heading = f"{paper.title}. {chunk.section}" if chunk.section else paper.title
    return f"{heading}\n{chunk.text}"


class VectorStore:
    def __init__(self, settings: Settings, embedder: Embedder, client: chromadb.ClientAPI | None = None):
        self.embedder = embedder
        self.client = client or chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,
        )

    def count(self) -> int:
        return self.collection.count()

    def remove_paper(self, paper_id: str) -> None:
        self.collection.delete(where={"paper_id": paper_id})

    def index_paper(self, paper: Paper) -> int:
        self.remove_paper(paper.id)
        chunks = list(paper.chunks)
        if not chunks:
            return 0
        vectors = self.embedder.embed([embedding_text(paper, chunk) for chunk in chunks])
        self.collection.add(
            ids=[chunk.id for chunk in chunks],
            embeddings=vectors,
            documents=[chunk.text for chunk in chunks],
            metadatas=[
                {
                    "paper_id": paper.id,
                    "chunk_index": chunk.chunk_index,
                    "section": chunk.section or "",
                    "page": chunk.page or 0,
                    "source": chunk.source,
                    "published_ts": int(paper.published_at.timestamp()),
                }
                for chunk in chunks
            ],
        )
        return len(chunks)

    def search(self, text: str, k: int, paper_ids: list[str] | None = None) -> list[VectorHit]:
        [vector] = self.embedder.embed([text])
        return self.search_vector(vector, k, paper_ids)

    def search_vector(self, vector: list[float], k: int, paper_ids: list[str] | None = None) -> list[VectorHit]:
        if k <= 0 or self.count() == 0:
            return []
        where = None
        if paper_ids is not None:
            if not paper_ids:
                return []
            where = {"paper_id": {"$in": list(paper_ids)}}
        result = self.collection.query(
            query_embeddings=[vector],
            n_results=min(k, self.count()),
            where=where,
            include=["distances", "metadatas"],
        )
        return [
            VectorHit(
                chunk_id=chunk_id,
                paper_id=metadata["paper_id"],
                similarity=max(0.0, min(1.0, 1.0 - distance)),
            )
            for chunk_id, distance, metadata in zip(
                result["ids"][0], result["distances"][0], result["metadatas"][0]
            )
        ]
