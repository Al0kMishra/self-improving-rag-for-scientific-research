import importlib.util
from argparse import Namespace
from pathlib import Path

import pytest

from app.models import ExperimentRun, WeightSnapshot
from tests.factories import make_paper, make_query, uniform_scores

RUNNER = Path(__file__).resolve().parents[1] / "evaluation" / "run_experiment.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("run_experiment", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add(db, paper, mode, cycle, score, phase="train", chunks=None, run="exp"):
    record = make_query(db, paper, mode=mode, scores=uniform_scores(score))
    record.experiment_run, record.cycle, record.phase = run, cycle, phase
    if chunks is not None:
        record.retrieved = [r for r in record.retrieved if r.chunk_id in chunks]
    db.commit()
    return record


@pytest.fixture
def experiment(db):
    paper = make_paper(db, chunk_texts=("a", "b", "c"))
    db.add(ExperimentRun(id="exp", config={"cycles": 2}))
    add(db, paper, "baseline", 0, 0.4)
    first = add(db, paper, "proposed", 0, 0.5, chunks={"2401.00001#0", "2401.00001#1"})
    db.add(WeightSnapshot(alpha=0.6, beta=0.25, gamma=0.15, trigger="evaluation", experiment_run="exp",
                          query_id=first.id))
    second = add(db, paper, "proposed", 1, 0.7, chunks={"2401.00001#0", "2401.00001#2"})
    db.add(WeightSnapshot(alpha=0.55, beta=0.3, gamma=0.15, trigger="evaluation", experiment_run="exp",
                          query_id=second.id))
    add(db, paper, "baseline", 2, 0.3, phase="test")
    add(db, paper, "proposed", 2, 0.6, phase="test")
    db.commit()
    return paper


def test_list_experiments(client, experiment):
    [run] = client.get("/api/experiments").json()
    assert run["experiment_run"] == "exp"
    assert (run["queries"], run["completed"], run["cycles"]) == (5, 5, 3)
    assert run["modes"] == ["baseline", "proposed"]
    assert run["config"] == {"cycles": 2}


def test_cycle_metrics(client, experiment):
    body = client.get("/api/experiments/exp/cycles").json()
    rows = {(c["cycle"], c["mode"], c["phase"]): c["means"]["overall"] for c in body["cycles"]}
    assert rows == {
        (0, "baseline", "train"): pytest.approx(0.4),
        (0, "proposed", "train"): pytest.approx(0.5),
        (1, "proposed", "train"): pytest.approx(0.7),
        (2, "baseline", "test"): pytest.approx(0.3),
        (2, "proposed", "test"): pytest.approx(0.6),
    }
    weights = [(w["cycle"], w["alpha"]) for w in body["weights"]]
    assert weights == [(-1, 0.7), (0, 0.6), (1, 0.55), (2, 0.55)]
    [change] = body["retrieval_change"]
    assert change["cycle"] == 1
    assert change["mean_topk_jaccard_vs_previous"] == pytest.approx(1 / 3)


def test_unknown_experiment(client):
    assert client.get("/api/experiments/nope/cycles").status_code == 404


def test_runner_plan():
    runner = load_runner()
    questions = [{"question": "q1", "paraphrase": "p1"}, {"question": "q2", "paraphrase": "p2"}]
    args = Namespace(cycles=2, baseline_cycles=1, test="paraphrase", test_limit=1)
    steps = runner.plan(args, questions)
    assert steps[:3] == [("q1", "baseline", 0, "train", False), ("q1", "proposed", 0, "train", True),
                         ("q2", "baseline", 0, "train", False)]
    assert ("q1", "baseline", 1, "train", False) not in steps
    assert steps[-2:] == [("p1", "baseline", 2, "test", False), ("p1", "proposed", 2, "test", False)]
    assert len(steps) == 8


def test_questions_file():
    import json

    questions = json.loads((RUNNER.parent / "questions.json").read_text())
    assert len(questions) >= 20
    assert all(q["question"] != q["paraphrase"] for q in questions)
    assert len({q["id"] for q in questions}) == len(questions)


def load_plotter():
    spec = importlib.util.spec_from_file_location("plot_results", RUNNER.parent / "plot_results.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_plotter_builds_report_from_exported_files(client, experiment, settings, db, tmp_path, monkeypatch):
    runner = load_runner()
    folder = runner.export(db, settings, "exp", tmp_path)
    plotter = load_plotter()
    monkeypatch.setattr("sys.argv", ["plot_results.py", "exp", "--results", str(tmp_path)])
    plotter.main()
    for name in ("metrics_by_cycle.png", "weights.png", "retrieval_change.png", "latency.png", "report.md"):
        assert (folder / name).exists(), name
    report = (folder / "report.md").read_text()
    assert "| 1 | train | baseline | 1 |" in report
    assert "| overall | 0.300 | 0.600 | +0.300 |" in report
    assert (folder / "test_comparison.png").exists()


def test_bootstrap_ci_brackets_the_mean():
    plotter = load_plotter()
    low, high = plotter.bootstrap_ci([0.1, 0.2, 0.3, 0.4])
    assert low <= 0.25 <= high
    assert plotter.bootstrap_ci([]) is None
