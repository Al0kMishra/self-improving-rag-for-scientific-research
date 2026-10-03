from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import METRIC_FIELDS, MODES, Evaluation, Feedback, QueryRecord
from app.schemas.metrics import MetricMeans, ModeMetrics

SCORE_FIELDS = (*METRIC_FIELDS, "overall")


def _filtered(stmt, experiment_run: str | None):
    stmt = stmt.where(QueryRecord.status == "completed")
    if experiment_run is not None:
        stmt = stmt.where(QueryRecord.experiment_run == experiment_run)
    return stmt


def mode_metrics(session: Session, experiment_run: str | None = None) -> list[ModeMetrics]:
    score_stmt = _filtered(
        select(
            QueryRecord.mode,
            func.count(QueryRecord.id),
            func.count(Evaluation.id),
            func.avg(QueryRecord.total_ms),
            *(func.avg(getattr(Evaluation, name)) for name in SCORE_FIELDS),
        )
        .outerjoin(Evaluation, Evaluation.query_id == QueryRecord.id)
        .group_by(QueryRecord.mode),
        experiment_run,
    )
    feedback_stmt = _filtered(
        select(
            QueryRecord.mode,
            func.sum(case((Feedback.rating == 1, 1), else_=0)),
            func.sum(case((Feedback.rating == -1, 1), else_=0)),
        )
        .join(Feedback, Feedback.query_id == QueryRecord.id)
        .group_by(QueryRecord.mode),
        experiment_run,
    )

    scores = {row[0]: row[1:] for row in session.execute(score_stmt)}
    feedback = {row[0]: row[1:] for row in session.execute(feedback_stmt)}

    results = []
    for mode in MODES:
        queries, evaluated, latency, *means = scores.get(mode, (0, 0, None, *([None] * len(SCORE_FIELDS))))
        positive, negative = feedback.get(mode, (0, 0))
        results.append(
            ModeMetrics(
                mode=mode,
                queries=queries,
                evaluated=evaluated,
                mean_latency_ms=latency,
                means=MetricMeans(**dict(zip(SCORE_FIELDS, means))),
                positive_feedback=positive or 0,
                negative_feedback=negative or 0,
            )
        )
    return results
