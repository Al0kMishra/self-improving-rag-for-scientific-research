import argparse
import csv
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import create_db_engine, create_session_factory, utcnow  # noqa: E402
from app.models import ExperimentRun, QueryRecord, create_tables  # noqa: E402
from app.services.container import build_services  # noqa: E402
from app.services.experiments import experiment_cycles  # noqa: E402
from app.services.weights import ensure_initial_snapshot  # noqa: E402

logger = logging.getLogger("experiment")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Baseline vs Self-Improving RAG experiment.")
    parser.add_argument("--run-id", default=f"exp-{datetime.now():%Y%m%d-%H%M}")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation" / "questions.json")
    parser.add_argument("--limit", type=int, default=None, help="use only the first N questions")
    parser.add_argument("--cycles", type=int, default=3, help="feedback cycles for the proposed system")
    parser.add_argument("--baseline-cycles", type=int, default=1, help="cycles to measure the baseline in")
    parser.add_argument("--test", choices=["paraphrase", "none"], default="paraphrase")
    parser.add_argument("--test-limit", type=int, default=None, help="use only the first N paraphrases")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation" / "results")
    return parser.parse_args()


def already_done(session, run, text, mode, cycle, phase) -> bool:
    stmt = select(QueryRecord.id).where(
        QueryRecord.experiment_run == run,
        QueryRecord.text == text,
        QueryRecord.mode == mode,
        QueryRecord.cycle == cycle,
        QueryRecord.phase == phase,
        QueryRecord.status == "completed",
    )
    return session.scalars(stmt.limit(1)).first() is not None


def plan(args, questions) -> list[tuple[str, str, int, str, bool]]:
    steps = []
    for cycle in range(args.cycles):
        for question in questions:
            if cycle < args.baseline_cycles:
                steps.append((question["question"], "baseline", cycle, "train", False))
            steps.append((question["question"], "proposed", cycle, "train", True))
    if args.test == "paraphrase":
        test_cycle = args.cycles
        for question in questions[: args.test_limit]:
            for mode in ("baseline", "proposed"):
                steps.append((question["paraphrase"], mode, test_cycle, "test", False))
    return steps


def warm_up(session, services, texts) -> None:
    for index, text in enumerate(texts, start=1):
        started = time.perf_counter()
        services.retrieval.run(session, text, "baseline")
        logger.info("warm-up %d/%d in %.0fs: %s", index, len(texts), time.perf_counter() - started, text)


def export(session, settings, run, output: Path) -> Path:
    folder = output / run
    folder.mkdir(parents=True, exist_ok=True)
    records = session.scalars(
        select(QueryRecord).where(QueryRecord.experiment_run == run).order_by(QueryRecord.id)
    ).all()
    fields = [
        "id", "phase", "cycle", "mode", "status", "text", "alpha", "beta", "gamma",
        "retrieval_precision", "retrieval_relevance", "groundedness", "citation_accuracy",
        "answer_relevance", "evidence_coverage", "overall",
        "retrieval_ms", "generation_ms", "evaluation_ms", "total_ms", "citations", "invalid_citations", "error",
    ]
    with (folder / "queries.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            evaluation = record.evaluation
            row = {name: getattr(record, name, None) for name in fields}
            for name in fields[9:16]:
                row[name] = getattr(evaluation, name) if evaluation else None
            row["citations"] = len(record.citations)
            row["invalid_citations"] = len(record.invalid_citations or [])
            writer.writerow(row)
    summary = experiment_cycles(session, settings, run).model_dump(mode="json")
    run_row = session.get(ExperimentRun, run)
    summary["config"] = run_row.config if run_row else {}
    (folder / "summary.json").write_text(json.dumps(summary, indent=2))
    return folder


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings().model_copy(update={"arxiv_cache_ttl_hours": 24 * 365})
    settings.ensure_dirs()
    services = build_services(settings)
    if services.query_pipeline is None:
        sys.exit("No LLM configured. Set LLM_API_KEY (anthropic) or LLM_PROVIDER/LLM_BASE_URL in .env.")

    questions = json.loads(args.questions.read_text())[: args.limit]
    engine = create_db_engine(settings.database_url)
    create_tables(engine)
    sessions = create_session_factory(engine)

    with sessions() as session:
        run = session.get(ExperimentRun, args.run_id)
        if run is None:
            run = ExperimentRun(
                id=args.run_id,
                config={
                    "questions": len(questions),
                    "cycles": args.cycles,
                    "baseline_cycles": args.baseline_cycles,
                    "test": args.test,
                    "test_limit": args.test_limit,
                    "llm": settings.generator_endpoint.label,
                    "evaluator": settings.evaluator_endpoint.label,
                    "embedding_model": settings.embedding_model,
                    "top_k": settings.retrieval_top_k,
                    "initial_weights": [settings.alpha_init, settings.beta_init, settings.gamma_init],
                    "weight_bounds": [settings.weight_min, settings.weight_max],
                    "learning_rate": settings.weight_learning_rate,
                },
            )
            session.add(run)
            session.commit()
        ensure_initial_snapshot(session, settings, args.run_id)

        steps = plan(args, questions)
        texts = list(dict.fromkeys(step[0] for step in steps))
        warm_up(session, services, texts)

        started = time.perf_counter()
        for index, (text, mode, cycle, phase, learn) in enumerate(steps, start=1):
            if already_done(session, args.run_id, text, mode, cycle, phase):
                continue
            record = services.query_pipeline.run(
                session, text, mode, experiment_run=args.run_id, cycle=cycle, learn=learn, phase=phase
            )
            overall = record.evaluation.overall if record.evaluation else None
            logger.info(
                "[%d/%d] %s cycle %d %s: %s overall=%s in %.0fs (elapsed %.0f min)",
                index, len(steps), phase, cycle, mode, record.status,
                f"{overall:.3f}" if overall is not None else "n/a",
                (record.total_ms or 0) / 1000, (time.perf_counter() - started) / 60,
            )

        run.status = "finished"
        run.finished_at = utcnow()
        session.commit()
        folder = export(session, settings, args.run_id, args.output)
        logger.info("results written to %s", folder)


if __name__ == "__main__":
    main()
