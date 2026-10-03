from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.metrics import MetricsResponse
from app.services.metrics import mode_metrics

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", response_model=MetricsResponse)
def get_metrics(experiment_run: str | None = None, db: Session = Depends(get_db)) -> MetricsResponse:
    return MetricsResponse(experiment_run=experiment_run, modes=mode_metrics(db, experiment_run))
