import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import QueryRecord, WeightSnapshot
from app.services.weights import RankingWeights, current_weights

logger = logging.getLogger(__name__)

COMPONENTS = ("semantic", "recency", "feedback")


@dataclass
class LabelledChunk:
    semantic: float
    recency: float
    feedback: float
    relevance: float


@dataclass
class Update:
    before: RankingWeights
    after: RankingWeights
    slopes: dict[str, float]
    target: dict[str, float] | None
    learning_rate: float
    labels: int
    reason: str

    @property
    def changed(self) -> bool:
        return self.target is not None


def slope(values: list[float], labels: list[float]) -> float:
    n = len(values)
    mean_v, mean_l = sum(values) / n, sum(labels) / n
    variance = sum((l - mean_l) ** 2 for l in labels) / n
    if variance < 1e-12:
        return 0.0
    covariance = sum((v - mean_v) * (l - mean_l) for v, l in zip(values, labels)) / n
    return covariance / variance


def project_to_bounds(weights: list[float], low: float, high: float) -> list[float]:
    def clipped(shift: float) -> list[float]:
        return [min(max(w - shift, low), high) for w in weights]

    lower, upper = min(weights) - high, max(weights) - low
    for _ in range(100):
        shift = (lower + upper) / 2
        if sum(clipped(shift)) > 1.0:
            lower = shift
        else:
            upper = shift
    return clipped((lower + upper) / 2)


def compute_update(
    weights: RankingWeights,
    chunks: list[LabelledChunk],
    learning_rate: float,
    low: float,
    high: float,
    min_labels: int,
) -> Update:
    slopes = {name: 0.0 for name in COMPONENTS}

    def unchanged(reason: str) -> Update:
        return Update(weights, weights, slopes, None, learning_rate, len(chunks), reason)

    if len(chunks) < min_labels:
        return unchanged(f"only {len(chunks)} labelled chunks, need {min_labels}")
    labels = [c.relevance for c in chunks]
    if max(labels) - min(labels) < 1e-9:
        return unchanged("all labelled chunks have the same relevance, no contrast to learn from")

    slopes = {name: slope([getattr(c, name) for c in chunks], labels) for name in COMPONENTS}
    positive = {name: max(value, 0.0) for name, value in slopes.items()}
    total = sum(positive.values())
    if total < 1e-9:
        return unchanged("no component scored higher on relevant chunks")

    target = {name: value / total for name, value in positive.items()}
    current = [weights.alpha, weights.beta, weights.gamma]
    blended = [(1 - learning_rate) * w + learning_rate * target[name] for w, name in zip(current, COMPONENTS)]
    alpha, beta, gamma = project_to_bounds(blended, low, high)
    return Update(
        weights, RankingWeights(alpha, beta, gamma), slopes, target, learning_rate, len(chunks),
        "moved toward the components that separate relevant from irrelevant evidence",
    )


def labelled_chunks(record: QueryRecord, overrides: dict[str, float] | None = None) -> list[LabelledChunk]:
    overrides = overrides or {}
    chunks = []
    for item in record.retrieved:
        relevance = overrides.get(item.chunk_id, item.judged_relevance)
        if relevance is None:
            continue
        chunks.append(LabelledChunk(item.semantic_score, item.recency_score, item.feedback_score, relevance))
    return chunks


class WeightAdapter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def update(
        self,
        session: Session,
        record: QueryRecord,
        trigger: str,
        overrides: dict[str, float] | None = None,
        learning_rate: float | None = None,
    ) -> Update | None:
        if record.mode != "proposed" or record.status != "completed":
            return None
        weights = current_weights(session, self.settings, record.experiment_run)
        update = compute_update(
            weights,
            labelled_chunks(record, overrides),
            learning_rate or self.settings.weight_learning_rate,
            self.settings.weight_min,
            self.settings.weight_max,
            self.settings.adaptation_min_labels,
        )
        if update.changed:
            session.add(
                WeightSnapshot(
                    alpha=update.after.alpha,
                    beta=update.after.beta,
                    gamma=update.after.gamma,
                    trigger=trigger,
                    experiment_run=record.experiment_run,
                    query_id=record.id,
                    signal=record.evaluation.retrieval_relevance if record.evaluation else None,
                    note=update.reason,
                    details={
                        "before": vars(update.before),
                        "slopes": update.slopes,
                        "target": update.target,
                        "learning_rate": update.learning_rate,
                        "labels": update.labels,
                    },
                )
            )
        logger.info("weight update after query %s (%s): %s", record.id, trigger, update.reason)
        return update

    def on_feedback(self, session: Session, record: QueryRecord, rating: int, chunk_id: str | None) -> Update | None:
        label = 1.0 if rating > 0 else 0.0
        if chunk_id is not None:
            overrides = {chunk_id: label}
        else:
            overrides = {citation.chunk_id: label for citation in record.citations}
        update = self.update(session, record, "feedback", overrides)
        session.commit()
        return update
