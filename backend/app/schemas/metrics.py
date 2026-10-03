from pydantic import BaseModel


class MetricMeans(BaseModel):
    retrieval_precision: float | None
    retrieval_relevance: float | None
    groundedness: float | None
    citation_accuracy: float | None
    answer_relevance: float | None
    evidence_coverage: float | None
    overall: float | None


class ModeMetrics(BaseModel):
    mode: str
    queries: int
    evaluated: int
    mean_latency_ms: float | None
    means: MetricMeans
    positive_feedback: int
    negative_feedback: int


class MetricsResponse(BaseModel):
    experiment_run: str | None
    modes: list[ModeMetrics]
