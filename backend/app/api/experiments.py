from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db
from app.core.config import Settings
from app.models import ExperimentRun, QueryRecord
from app.schemas.experiments import ExperimentCycles, ExperimentSummary
from app.services.experiments import experiment_cycles, list_experiments

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("", response_model=list[ExperimentSummary])
def get_experiments(db: Session = Depends(get_db)) -> list[ExperimentSummary]:
    return list_experiments(db)


@router.get("/{run}/cycles", response_model=ExperimentCycles)
def get_experiment_cycles(
    run: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> ExperimentCycles:
    known = db.get(ExperimentRun, run) or db.scalars(
        select(QueryRecord.id).where(QueryRecord.experiment_run == run).limit(1)
    ).first()
    if not known:
        raise HTTPException(status_code=404, detail=f"experiment {run} not found")
    return experiment_cycles(db, settings, run)
