from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import WeightSnapshot


@dataclass(frozen=True)
class RankingWeights:
    alpha: float
    beta: float
    gamma: float


def initial_weights(settings: Settings) -> RankingWeights:
    return RankingWeights(settings.alpha_init, settings.beta_init, settings.gamma_init)


def latest_snapshot(session: Session, experiment_run: str | None = None) -> WeightSnapshot | None:
    stmt = select(WeightSnapshot).where(WeightSnapshot.experiment_run.is_(None) if experiment_run is None
                                        else WeightSnapshot.experiment_run == experiment_run)
    return session.scalars(stmt.order_by(WeightSnapshot.id.desc()).limit(1)).first()


def current_weights(session: Session, settings: Settings, experiment_run: str | None = None) -> RankingWeights:
    snapshot = latest_snapshot(session, experiment_run)
    if snapshot is None:
        return initial_weights(settings)
    return RankingWeights(snapshot.alpha, snapshot.beta, snapshot.gamma)


def ensure_initial_snapshot(session: Session, settings: Settings, experiment_run: str | None = None) -> None:
    if latest_snapshot(session, experiment_run) is not None:
        return
    weights = initial_weights(settings)
    session.add(
        WeightSnapshot(
            alpha=weights.alpha,
            beta=weights.beta,
            gamma=weights.gamma,
            trigger="init",
            experiment_run=experiment_run,
            note="seeded from settings",
        )
    )
    session.commit()
