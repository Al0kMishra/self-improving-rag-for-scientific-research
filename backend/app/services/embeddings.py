import logging
import math
import os
import threading
from typing import Protocol

from app.core.config import Settings

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    model_name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    """
    Lightweight embedding implementation.

    Keeps the existing class name/interface so the rest of the
    application does not need to change.

    Uses FastEmbed/ONNX Runtime with the same
    sentence-transformers/all-MiniLM-L6-v2 model.
    """

    def __init__(self, settings: Settings):
        self.model_name = settings.embedding_model
        self.batch_size = min(settings.embedding_batch_size, 8)
        self.device = settings.embedding_device or None

        # Use the Render cache path when deployed, while still working locally.
        self.cache_dir = os.getenv(
            "FASTEMBED_CACHE_PATH",
            os.getenv("FASTEMBED_CACHE_DIR", ".fastembed"),
        )

        self.threads = 1
        self._model = None
        self._lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def _load(self):
        with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding

                logger.info(
                    "Loading lightweight embedding model %s "
                    "(threads=%d, batch_size=%d, cache_dir=%s)",
                    self.model_name,
                    self.threads,
                    self.batch_size,
                    self.cache_dir,
                )

                self._model = TextEmbedding(
                    model_name=self.model_name,
                    cache_dir=self.cache_dir,
                    threads=self.threads,
                )

        return self._model

    @staticmethod
    def _normalize(vector) -> list[float]:
        values = vector.tolist() if hasattr(vector, "tolist") else list(vector)

        norm = math.sqrt(sum(float(x) * float(x) for x in values))

        if norm == 0:
            return [float(x) for x in values]

        return [float(x) / norm for x in values]

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        model = self._load()

        vectors = model.embed(
            texts,
            batch_size=self.batch_size,
        )

        return [self._normalize(vector) for vector in vectors]