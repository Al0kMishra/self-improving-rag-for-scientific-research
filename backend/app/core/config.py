import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]

AI_ML_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.NE", "stat.ML"]


Provider = Literal["anthropic", "openai_compatible"]


@dataclass(frozen=True)
class LLMEndpoint:
    provider: Provider
    model: str
    api_key: str | None
    base_url: str | None

    @property
    def configured(self) -> bool:
        if self.provider == "openai_compatible":
            return bool(self.base_url)
        return bool(self.api_key or os.environ.get("ANTHROPIC_API_KEY"))

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_name: str = "Self-Improving RAG for Scientific Research Literature"
    environment: Literal["development", "test", "production"] = "development"
    cors_origins: list[str] = ["http://localhost:5173"]

    data_dir: Path = PROJECT_ROOT / "data"

    arxiv_categories: list[str] = Field(default_factory=lambda: list(AI_ML_CATEGORIES))
    arxiv_max_results: int = Field(20, ge=1, le=100)
    arxiv_recency_days: int | None = Field(1095, ge=1)
    arxiv_request_delay_seconds: float = Field(3.0, ge=0)
    arxiv_api_url: str = "https://export.arxiv.org/api/query"
    arxiv_timeout_seconds: float = Field(30.0, gt=0)
    arxiv_max_attempts: int = Field(5, ge=1, le=10)
    arxiv_backoff_seconds: float = Field(10.0, ge=0)
    arxiv_cache_ttl_hours: float = Field(24.0, ge=0)
    arxiv_min_results: int = Field(5, ge=0)
    arxiv_max_keywords: int = Field(5, ge=1, le=10)

    max_pdf_pages: int = Field(30, ge=1)
    pdf_max_papers_per_query: int = Field(8, ge=0)
    pdf_max_bytes: int = Field(25_000_000, ge=100_000)
    pdf_download_delay_seconds: float = Field(1.0, ge=0)
    min_extracted_chars: int = Field(2000, ge=0)
    chunk_size_chars: int = Field(1200, ge=200)
    chunk_overlap_chars: int = Field(200, ge=0)

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_batch_size: int = Field(32, ge=1)
    embedding_device: str | None = None
    chroma_collection: str = "chunks"
    retrieval_candidate_pool: int = Field(40, ge=1)
    retrieval_top_k: int = Field(8, ge=1)

    llm_provider: Provider = "anthropic"
    llm_model: str = "claude-opus-5"
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None
    llm_fallbacks: bool = True
    llm_temperature: float = Field(0.0, ge=0, le=1)
    llm_max_tokens: int = Field(16000, ge=256)
    llm_timeout_seconds: float = Field(300.0, gt=0)
    evaluator_provider: Provider | None = None
    evaluator_model: str | None = None
    evaluator_api_key: SecretStr | None = None
    evaluator_base_url: str | None = None

    alpha_init: float = Field(0.70, ge=0, le=1)
    beta_init: float = Field(0.15, ge=0, le=1)
    gamma_init: float = Field(0.15, ge=0, le=1)
    weight_min: float = Field(0.05, ge=0, le=1)
    weight_max: float = Field(0.90, ge=0, le=1)
    weight_learning_rate: float = Field(0.10, gt=0, le=0.5)
    adaptation_min_labels: int = Field(3, ge=2)
    recency_half_life_days: float = Field(365.0, gt=0)
    max_chunks_per_paper: int = Field(3, ge=1)
    feedback_prior_strength: float = Field(2.0, gt=0)
    feedback_similarity_threshold: float = Field(0.3, ge=0, lt=1)

    @model_validator(mode="after")
    def check_consistency(self) -> "Settings":
        if self.chunk_overlap_chars >= self.chunk_size_chars:
            raise ValueError("chunk_overlap_chars must be smaller than chunk_size_chars")
        if self.retrieval_top_k > self.retrieval_candidate_pool:
            raise ValueError("retrieval_top_k cannot exceed retrieval_candidate_pool")
        if not self.weight_min < self.weight_max:
            raise ValueError("weight_min must be smaller than weight_max")
        if not 3 * self.weight_min <= 1 <= 3 * self.weight_max:
            raise ValueError("weight bounds make alpha + beta + gamma = 1 impossible")
        for name in ("alpha_init", "beta_init", "gamma_init"):
            value = getattr(self, name)
            if not self.weight_min <= value <= self.weight_max:
                raise ValueError(f"{name}={value} is outside [{self.weight_min}, {self.weight_max}]")
        if abs(self.alpha_init + self.beta_init + self.gamma_init - 1) > 1e-6:
            raise ValueError("alpha_init + beta_init + gamma_init must sum to 1")
        if self.llm_provider == "openai_compatible" and not self.llm_base_url:
            raise ValueError("LLM_BASE_URL is required when LLM_PROVIDER=openai_compatible")
        evaluator = self.evaluator_endpoint
        if evaluator.provider == "openai_compatible" and not evaluator.base_url:
            raise ValueError("EVALUATOR_BASE_URL is required when the evaluator uses openai_compatible")
        if self.separate_evaluator and self.llm_configured and not evaluator.configured:
            raise ValueError("the evaluator uses a different provider, so EVALUATOR_API_KEY is required")
        unknown = set(self.arxiv_categories) - set(AI_ML_CATEGORIES)
        if unknown:
            raise ValueError(f"unsupported arXiv categories: {sorted(unknown)}")
        return self

    @property
    def generator_endpoint(self) -> LLMEndpoint:
        return LLMEndpoint(
            provider=self.llm_provider,
            model=self.llm_model,
            api_key=self.llm_api_key.get_secret_value() if self.llm_api_key else None,
            base_url=self.llm_base_url,
        )

    @property
    def evaluator_endpoint(self) -> LLMEndpoint:
        generator = self.generator_endpoint
        provider = self.evaluator_provider or generator.provider
        same_provider = provider == generator.provider
        return LLMEndpoint(
            provider=provider,
            model=self.evaluator_model or generator.model,
            api_key=self.evaluator_api_key.get_secret_value() if self.evaluator_api_key
            else generator.api_key if same_provider else None,
            base_url=self.evaluator_base_url or (generator.base_url if same_provider else None),
        )

    @property
    def separate_evaluator(self) -> bool:
        return self.evaluator_endpoint != self.generator_endpoint

    @property
    def llm_configured(self) -> bool:
        return self.generator_endpoint.configured

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "rag.db"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.sqlite_path}"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def pdf_dir(self) -> Path:
        return self.data_dir / "pdfs"

    @property
    def paper_cache_dir(self) -> Path:
        return self.data_dir / "papers"

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.chroma_dir, self.pdf_dir, self.paper_cache_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
