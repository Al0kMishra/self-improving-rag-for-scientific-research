from collections import defaultdict

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Evaluation, ExperimentRun, QueryRecord, RetrievedChunk, WeightSnapshot
from app.schemas.experiments import (
    CycleMetrics,
    CycleWeights,
    ExperimentCycles,
    ExperimentSummary,
    RetrievalChange,
)
from app.schemas.metrics import MetricMeans
from app.services.metrics import SCORE_FIELDS
from app.services.weights import initial_weights


def list_experiments(session: Session) -> list[ExperimentSummary]:
    runs = {run.id: run for run in session.scalars(select(ExperimentRun))}
    rows = session.execute(
        select(
            QueryRecord.experiment_run,
            func.count(QueryRecord.id),
            func.sum(case((QueryRecord.status == "completed", 1), else_=0)),
            func.max(QueryRecord.cycle),
            func.group_concat(QueryRecord.mode.distinct()),
            func.min(QueryRecord.created_at),
        )
        .where(QueryRecord.experiment_run.is_not(None))
        .group_by(QueryRecord.experiment_run)
    ).all()
    counted = {row[0]: row for row in rows}
    summaries = []
    for name in sorted(set(runs) | set(counted)):
        run = runs.get(name)
        _, queries, completed, max_cycle, modes, first = counted.get(name, (name, 0, 0, None, "", None))
        summaries.append(
            ExperimentSummary(
                experiment_run=name,
                status=run.status if run else "unknown",
                created_at=run.created_at if run else first,
                finished_at=run.finished_at if run else None,
                queries=queries,
                completed=completed or 0,
                cycles=(max_cycle + 1) if max_cycle is not None else 0,
                modes=sorted(filter(None, (modes or "").split(","))),
                config=run.config if run else {},
            )
        )
    return sorted(summaries, key=lambda s: s.created_at or 0, reverse=True)


def cycle_metrics(session: Session, run: str) -> list[CycleMetrics]:
    stmt = (
        select(
            QueryRecord.cycle,
            QueryRecord.mode,
            func.coalesce(QueryRecord.phase, "train"),
            func.count(QueryRecord.id),
            func.count(Evaluation.id),
            func.avg(QueryRecord.total_ms),
            func.avg(QueryRecord.generation_ms),
            *(func.avg(getattr(Evaluation, name)) for name in SCORE_FIELDS),
        )
        .outerjoin(Evaluation, Evaluation.query_id == QueryRecord.id)
        .where(QueryRecord.experiment_run == run, QueryRecord.status == "completed")
        .group_by(QueryRecord.cycle, QueryRecord.mode, func.coalesce(QueryRecord.phase, "train"))
        .order_by(QueryRecord.cycle, QueryRecord.mode)
    )
    return [
        CycleMetrics(
            cycle=cycle,
            mode=mode,
            phase=phase,
            queries=queries,
            evaluated=evaluated,
            mean_latency_ms=latency,
            mean_generation_ms=generation,
            means=MetricMeans(**dict(zip(SCORE_FIELDS, means))),
        )
        for cycle, mode, phase, queries, evaluated, latency, generation, *means in session.execute(stmt)
        if cycle is not None
    ]


def weights_by_cycle(session: Session, settings: Settings, run: str, cycles: list[int]) -> list[CycleWeights]:
    rows = session.execute(
        select(WeightSnapshot, QueryRecord.cycle)
        .outerjoin(QueryRecord, QueryRecord.id == WeightSnapshot.query_id)
        .where(WeightSnapshot.experiment_run == run)
        .order_by(WeightSnapshot.id)
    ).all()
    start = initial_weights(settings)
    result = [CycleWeights(cycle=-1, alpha=start.alpha, beta=start.beta, gamma=start.gamma)]
    latest = start
    for cycle in sorted(set(cycles)):
        for snapshot, snapshot_cycle in rows:
            if snapshot_cycle is not None and snapshot_cycle <= cycle:
                latest = snapshot
        result.append(CycleWeights(cycle=cycle, alpha=latest.alpha, beta=latest.beta, gamma=latest.gamma))
    return result


def retrieval_change(session: Session, run: str) -> list[RetrievalChange]:
    rows = session.execute(
        select(QueryRecord.cycle, QueryRecord.text, RetrievedChunk.chunk_id)
        .join(RetrievedChunk, RetrievedChunk.query_id == QueryRecord.id)
        .where(
            QueryRecord.experiment_run == run,
            QueryRecord.mode == "proposed",
            QueryRecord.status == "completed",
            func.coalesce(QueryRecord.phase, "train") == "train",
        )
    )
    top_k: dict[int, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for cycle, text, chunk_id in rows:
        top_k[cycle][text].add(chunk_id)
    changes = []
    ordered = sorted(top_k)
    for previous, current in zip(ordered, ordered[1:]):
        shared = set(top_k[previous]) & set(top_k[current])
        if not shared:
            continue
        scores = [
            len(top_k[previous][q] & top_k[current][q]) / len(top_k[previous][q] | top_k[current][q])
            for q in shared
        ]
        changes.append(
            RetrievalChange(cycle=current, mean_topk_jaccard_vs_previous=sum(scores) / len(scores), questions=len(shared))
        )
    return changes


def experiment_cycles(session: Session, settings: Settings, run: str) -> ExperimentCycles:
    cycles = cycle_metrics(session, run)
    return ExperimentCycles(
        experiment_run=run,
        cycles=cycles,
        weights=weights_by_cycle(session, settings, run, [c.cycle for c in cycles]),
        retrieval_change=retrieval_change(session, run),
    )
