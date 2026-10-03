import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.services.embeddings import SentenceTransformerEmbedder  # noqa: E402

embedder = SentenceTransformerEmbedder(get_settings())
print(f"{embedder.model_name}: {len(embedder.embed(['warm up'])[0])} dimensions")
