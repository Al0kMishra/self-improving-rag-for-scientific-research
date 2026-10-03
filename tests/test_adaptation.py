import pytest

from app.models import WeightSnapshot
from app.services.adaptation import LabelledChunk, compute_update, project_to_bounds, slope
from app.services.weights import RankingWeights, current_weights
from tests.factories import make_paper, make_query, uniform_scores

W = RankingWeights(0.7, 0.15, 0.15)


def test_slope_is_mean_difference_for_binary_labels():
    assert slope([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0]) == pytest.approx(0.85 - 0.15)
    assert slope([0.5, 0.5], [1, 0]) == 0.0
    assert slope([0.1, 0.9], [1, 1]) == 0.0


@pytest.mark.parametrize(
    "weights",
    [[0.95, 0.03, 0.02], [0.2, 0.2, 0.2], [0.5, 0.5, 0.5], [1.0, 0.0, 0.0]],
)
def test_projection_respects_bounds_and_sums_to_one(weights):
    projected = project_to_bounds(weights, 0.05, 0.9)
    assert sum(projected) == pytest.approx(1.0)
    assert all(0.05 - 1e-9 <= w <= 0.9 + 1e-9 for w in projected)


def test_projection_keeps_feasible_weights():
    assert project_to_bounds([0.7, 0.15, 0.15], 0.05, 0.9) == pytest.approx([0.7, 0.15, 0.15])


def chunks(rows):
    return [LabelledChunk(*row) for row in rows]


def test_update_moves_toward_discriminative_component():
    recency_matters = chunks([(0.9, 0.9, 0.5, 1), (0.8, 0.8, 0.5, 1), (0.85, 0.1, 0.5, 0), (0.9, 0.2, 0.5, 0)])
    update = compute_update(W, recency_matters, 0.1, 0.05, 0.9, 3)
    assert update.changed
    assert update.slopes["recency"] > 0 and update.slopes["feedback"] == 0
    assert update.after.beta > W.beta and update.after.alpha < W.alpha
    assert update.after.alpha + update.after.beta + update.after.gamma == pytest.approx(1.0)
    assert abs(update.after.beta - W.beta) <= 0.1 + 1e-9


def test_update_is_bounded_after_many_steps():
    weights = W
    data = chunks([(0.1, 0.9, 0.5, 1), (0.1, 0.8, 0.5, 1), (0.9, 0.1, 0.5, 0)])
    for _ in range(200):
        weights = compute_update(weights, data, 0.1, 0.05, 0.9, 3).after
    assert weights.beta == pytest.approx(0.9, abs=1e-6)
    assert weights.alpha == pytest.approx(0.05, abs=1e-6) and weights.gamma == pytest.approx(0.05, abs=1e-6)


@pytest.mark.parametrize(
    ("rows", "reason"),
    [
        ([(0.9, 0.9, 0.5, 1)], "only 1 labelled"),
        ([(0.9, 0.9, 0.5, 1)] * 3, "same relevance"),
        ([(0.1, 0.1, 0.5, 1), (0.9, 0.9, 0.5, 0), (0.5, 0.5, 0.5, 0)], "no component"),
    ],
)
def test_no_update_without_signal(rows, reason):
    update = compute_update(W, chunks(rows), 0.1, 0.05, 0.9, 3)
    assert not update.changed and update.after == W
    assert reason in update.reason


def evaluated_query(db, paper, mode="proposed", experiment_run=None):
    record = make_query(db, paper, mode=mode, scores=uniform_scores(0.5))
    record.experiment_run = experiment_run
    record.retrieved[0].judged_relevance, record.retrieved[0].recency_score = 1.0, 0.9
    record.retrieved[1].judged_relevance, record.retrieved[1].recency_score = 0.0, 0.1
    db.commit()
    return record


def test_adapter_records_snapshot(services, db, settings):
    paper = make_paper(db, chunk_texts=("a", "b", "c"))
    record = evaluated_query(db, paper)
    record.retrieved[2].judged_relevance = 0.0
    db.commit()
    update = services.adapter.update(db, record, "evaluation")
    db.commit()
    snapshot = db.query(WeightSnapshot).order_by(WeightSnapshot.id.desc()).first()
    assert snapshot.trigger == "evaluation" and snapshot.query_id == record.id
    assert (snapshot.alpha, snapshot.beta, snapshot.gamma) == (update.after.alpha, update.after.beta, update.after.gamma)
    assert set(snapshot.details) == {"before", "slopes", "target", "learning_rate", "labels"}
    assert current_weights(db, settings) == update.after


def test_adapter_ignores_baseline_and_scopes_runs(services, db, settings):
    paper = make_paper(db, chunk_texts=("a", "b", "c"))
    assert services.adapter.update(db, evaluated_query(db, paper, mode="baseline"), "evaluation") is None
    record = evaluated_query(db, paper, experiment_run="exp")
    record.retrieved[2].judged_relevance = 0.0
    db.commit()
    services.adapter.update(db, record, "evaluation")
    db.commit()
    assert current_weights(db, settings, "exp") != current_weights(db, settings)
    assert current_weights(db, settings) == RankingWeights(0.7, 0.15, 0.15)


def test_feedback_triggers_update(client, db):
    paper = make_paper(db, chunk_texts=("a", "b", "c"))
    record = make_query(db, paper, scores=uniform_scores(0.5), cited=(0,))
    for item, recency in zip(record.retrieved, (0.9, 0.2, 0.1)):
        item.recency_score = recency
        item.judged_relevance = 0.5
    db.commit()
    client.post("/api/feedback", json={"query_id": record.id, "rating": 1})
    history = client.get("/api/improvement/history").json()
    assert history["snapshots"][-1]["trigger"] == "feedback"
    assert history["current"]["beta"] > 0.15
