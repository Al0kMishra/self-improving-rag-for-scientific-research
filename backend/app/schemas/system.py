from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ComponentStatus(BaseModel):
    status: Literal["ok", "not_configured", "error"]
    detail: str


class RankingConfig(BaseModel):
    alpha_init: float
    beta_init: float
    gamma_init: float
    weight_min: float
    weight_max: float
    learning_rate: float
    recency_half_life_days: float


class RetrievalConfig(BaseModel):
    arxiv_categories: list[str]
    arxiv_max_results: int
    arxiv_recency_days: int | None
    embedding_model: str
    candidate_pool: int
    top_k: int


class LLMConfig(BaseModel):
    provider: str
    model: str
    api_key_configured: bool


class SystemStatus(BaseModel):
    app_name: str
    version: str
    environment: str
    server_time: datetime
    components: dict[str, ComponentStatus]
    counts: dict[str, int]
    retrieval: RetrievalConfig
    ranking: RankingConfig
    llm: LLMConfig
