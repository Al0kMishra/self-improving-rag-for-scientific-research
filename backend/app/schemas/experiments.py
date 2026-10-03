from datetime import datetime

from pydantic import BaseModel

from app.schemas.metrics import MetricMeans


class ExperimentSummary(BaseModel):
    experiment_run: str
    status: str
    created_at: datetime | None
    finished_at: datetime | None
    queries: int
    completed: int
    cycles: int
    modes: list[str]
    config: dict


class CycleMetrics(BaseModel):
    cycle: int
    mode: str
    phase: str
    queries: int
    evaluated: int
    means: MetricMeans
    mean_latency_ms: float | None
    mean_generation_ms: float | None


class CycleWeights(BaseModel):
    cycle: int
    alpha: float
    beta: float
    gamma: float


class RetrievalChange(BaseModel):
    cycle: int
    mean_topk_jaccard_vs_previous: float
    questions: int


class ExperimentCycles(BaseModel):
    experiment_run: str
    cycles: list[CycleMetrics]
    weights: list[CycleWeights]
    retrieval_change: list[RetrievalChange]
