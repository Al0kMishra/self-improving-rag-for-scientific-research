from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Weights(BaseModel):
    alpha: float
    beta: float
    gamma: float


class WeightSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alpha: float
    beta: float
    gamma: float
    trigger: str
    experiment_run: str | None
    query_id: int | None
    signal: float | None
    note: str | None
    details: dict | None
    created_at: datetime


class ImprovementHistory(BaseModel):
    current: Weights
    weight_min: float
    weight_max: float
    learning_rate: float
    snapshots: list[WeightSnapshotOut]
