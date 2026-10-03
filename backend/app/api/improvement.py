from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db
from app.core.config import Settings
from app.models import WeightSnapshot
from app.schemas.weights import ImprovementHistory, Weights, WeightSnapshotOut
from app.services.weights import current_weights

router = APIRouter(prefix="/improvement", tags=["improvement"])


@router.get("/history", response_model=ImprovementHistory)
def improvement_history(
    limit: int = Query(200, ge=1, le=5000),
    experiment_run: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> ImprovementHistory:
    scope = (
        WeightSnapshot.experiment_run.is_(None)
        if experiment_run is None
        else WeightSnapshot.experiment_run == experiment_run
    )
    newest = db.scalars(
        select(WeightSnapshot).where(scope).order_by(WeightSnapshot.id.desc()).limit(limit)
    ).all()
    weights = current_weights(db, settings, experiment_run)
    return ImprovementHistory(
        current=Weights(alpha=weights.alpha, beta=weights.beta, gamma=weights.gamma),
        weight_min=settings.weight_min,
        weight_max=settings.weight_max,
        learning_rate=settings.weight_learning_rate,
        snapshots=[WeightSnapshotOut.model_validate(s) for s in reversed(newest)],
    )
