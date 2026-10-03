import argparse
import csv
import json
import random
from pathlib import Path
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = {"proposed": "#2a78d6", "baseline": "#eb6834"}
WEIGHT_COLORS = {"alpha": "#2a78d6", "beta": "#eb6834", "gamma": "#1baf7a"}
WEIGHT_LABELS = {"alpha": "α semantic", "beta": "β recency", "gamma": "γ feedback"}
METRICS = {
    "retrieval_precision": "Retrieval precision",
    "retrieval_relevance": "Retrieval relevance",
    "groundedness": "Groundedness",
    "citation_accuracy": "Citation accuracy",
    "answer_relevance": "Answer relevance",
    "evidence_coverage": "Evidence coverage",
}


def style(ax, title=None):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    if title:
        ax.set_title(title, color=TEXT, fontsize=11, loc="left")


def figure(width, height, rows=1, cols=1):
    fig, axes = plt.subplots(rows, cols, figsize=(width, height), facecolor=SURFACE, squeeze=False)
    return fig, axes


def load(folder: Path):
    summary = json.loads((folder / "summary.json").read_text())
    with (folder / "queries.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    return summary, rows


def number(value):
    return float(value) if value not in (None, "") else None


def train_cycles(summary):
    return sorted({c["cycle"] for c in summary["cycles"] if c["phase"] == "train"})


def plot_metrics_by_cycle(summary, folder: Path) -> Path:
    cycles = train_cycles(summary)
    fig, axes = figure(12, 6.5, 2, 3)
    for ax, (key, label) in zip(axes.flat, METRICS.items()):
        style(ax, label)
        for mode in ("baseline", "proposed"):
            points = [
                (c["cycle"], c["means"][key])
                for c in summary["cycles"]
                if c["mode"] == mode and c["phase"] == "train" and c["means"][key] is not None
            ]
            if not points:
                continue
            xs, ys = zip(*points)
            if mode == "baseline" and len(points) == 1:
                ax.axhline(ys[0], color=SERIES[mode], linewidth=2, linestyle=(0, (4, 3)))
                ax.annotate(f"baseline {ys[0]:.2f}", (cycles[-1], ys[0]), textcoords="offset points",
                            xytext=(0, 6), ha="right", fontsize=8, color=TEXT_SECONDARY)
            else:
                ax.plot(xs, ys, color=SERIES[mode], linewidth=2, marker="o", markersize=6,
                        markeredgecolor=SURFACE, markeredgewidth=2)
                ax.annotate(f"{ys[-1]:.2f}", (xs[-1], ys[-1]), textcoords="offset points", xytext=(6, -3),
                            fontsize=8, color=TEXT_SECONDARY)
        ax.set_xticks(cycles)
        ax.set_xticklabels([f"cycle {c + 1}" for c in cycles])
        ax.set_ylim(0, 1.05)
    handles = [
        plt.Line2D([], [], color=SERIES["proposed"], linewidth=2, marker="o", label="Self-improving RAG"),
        plt.Line2D([], [], color=SERIES["baseline"], linewidth=2, linestyle=(0, (4, 3)), label="Baseline RAG"),
    ]
    fig.legend(handles=handles, loc="upper right", frameon=False, fontsize=9, labelcolor=TEXT_SECONDARY)
    fig.suptitle("Evaluation scores across feedback cycles (training questions)", x=0.01, ha="left",
                 color=TEXT, fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    path = folder / "metrics_by_cycle.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def plot_weights(rows, summary, folder: Path) -> Path:
    proposed = [r for r in rows if r["mode"] == "proposed" and r["phase"] == "train" and r["status"] == "completed"]
    fig, axes = figure(9, 4)
    ax = axes[0][0]
    style(ax, "Ranking weights used for each proposed-mode query")
    xs = list(range(1, len(proposed) + 1))
    for key, color in WEIGHT_COLORS.items():
        ys = [float(r[key]) for r in proposed]
        if not ys:
            continue
        ax.plot(xs, ys, color=color, linewidth=2)
        ax.annotate(f"{WEIGHT_LABELS[key]} {ys[-1]:.2f}", (xs[-1], ys[-1]), textcoords="offset points",
                    xytext=(6, -3), fontsize=9, color=TEXT)
    boundaries = [i for i in range(1, len(proposed)) if proposed[i]["cycle"] != proposed[i - 1]["cycle"]]
    for boundary in boundaries:
        ax.axvline(boundary + 0.5, color=AXIS, linewidth=0.8, linestyle=(0, (2, 3)))
    ax.set_xlabel("proposed-mode query, in run order (dotted lines separate cycles)", color=TEXT_SECONDARY, fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_xlim(1, max(xs[-1] * 1.18 if xs else 1, 2))
    fig.tight_layout()
    path = folder / "weights.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def plot_latency(rows, folder: Path) -> Path:
    stages = [("retrieval_ms", "retrieval"), ("generation_ms", "generation"), ("evaluation_ms", "evaluation")]
    colors = ["#2a78d6", "#eb6834", "#1baf7a"]
    fig, axes = figure(8, 3.6)
    ax = axes[0][0]
    style(ax, "Mean latency per query by stage (seconds)")
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.grid(axis="y", visible=False)
    modes = ["baseline", "proposed"]
    for y, mode in enumerate(modes):
        left = 0.0
        completed = [r for r in rows if r["mode"] == mode and r["status"] == "completed"]
        for (key, label), color in zip(stages, colors):
            values = [number(r[key]) for r in completed if number(r[key]) is not None]
            width = mean(values) / 1000 if values else 0.0
            ax.barh(y, width, left=left, color=color, height=0.5, edgecolor=SURFACE, linewidth=2,
                    label=label if y == 0 else None)
            if width > 3:
                ax.text(left + width / 2, y, f"{width:.0f}", ha="center", va="center", fontsize=8, color=SURFACE)
            left += width
        ax.text(left, y, f"  {left:.0f}s total", va="center", fontsize=9, color=TEXT_SECONDARY)
    ax.set_yticks(range(len(modes)))
    ax.set_yticklabels(["Baseline RAG", "Self-improving RAG"])
    ax.legend(frameon=False, fontsize=9, loc="upper center", labelcolor=TEXT_SECONDARY, ncols=3,
              bbox_to_anchor=(0.5, -0.12))
    fig.tight_layout()
    path = folder / "latency.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def plot_retrieval_change(summary, folder: Path) -> Path | None:
    changes = summary.get("retrieval_change") or []
    if not changes:
        return None
    fig, axes = figure(6, 3.2)
    ax = axes[0][0]
    style(ax, "Top-k overlap with the previous cycle (same questions)")
    labels = [f"cycle {c['cycle']} → {c['cycle'] + 1}" for c in changes]
    values = [c["mean_topk_jaccard_vs_previous"] for c in changes]
    ax.bar(labels, values, color=SERIES["proposed"], width=0.5, edgecolor=SURFACE, linewidth=2)
    for x, value in enumerate(values):
        ax.text(x, value + 0.02, f"{value:.2f}", ha="center", fontsize=9, color=TEXT)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("mean Jaccard similarity", color=TEXT_SECONDARY, fontsize=9)
    fig.tight_layout()
    path = folder / "retrieval_change.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def paired_test_scores(rows):
    test = [r for r in rows if r["phase"] == "test" and r["status"] == "completed" and r["overall"]]
    by_question: dict[str, dict[str, dict]] = {}
    for row in test:
        by_question.setdefault(row["text"], {})[row["mode"]] = row
    return {q: modes for q, modes in by_question.items() if {"baseline", "proposed"} <= set(modes)}


def bootstrap_ci(differences, samples=10000, seed=7):
    if not differences:
        return None
    rng = random.Random(seed)
    means = sorted(mean(rng.choices(differences, k=len(differences))) for _ in range(samples))
    return means[int(0.025 * samples)], means[int(0.975 * samples)]


def plot_test_comparison(rows, folder: Path):
    pairs = paired_test_scores(rows)
    if not pairs:
        return None, {}
    stats = {}
    for key in (*METRICS, "overall"):
        baseline = [float(p["baseline"][key]) for p in pairs.values()]
        proposed = [float(p["proposed"][key]) for p in pairs.values()]
        differences = [b - a for a, b in zip(baseline, proposed)]
        stats[key] = {
            "baseline": mean(baseline),
            "proposed": mean(proposed),
            "difference": mean(differences),
            "ci95": bootstrap_ci(differences),
            "wins": sum(d > 1e-9 for d in differences),
            "losses": sum(d < -1e-9 for d in differences),
            "pairs": len(differences),
        }
    fig, axes = figure(9, 4.2)
    ax = axes[0][0]
    style(ax, f"Held-out paraphrased questions (n = {len(pairs)}), learning frozen")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    keys = list(METRICS)
    height = 0.36
    for offset, mode in ((-height / 2, "baseline"), (height / 2, "proposed")):
        values = [stats[k][mode] for k in keys]
        positions = [i + offset for i in range(len(keys))]
        ax.barh(positions, values, height=height, color=SERIES[mode], edgecolor=SURFACE, linewidth=2,
                label="Baseline RAG" if mode == "baseline" else "Self-improving RAG")
        for y, value in zip(positions, values):
            ax.text(value + 0.01, y, f"{value:.2f}", va="center", fontsize=8, color=TEXT_SECONDARY)
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels([METRICS[k] for k in keys])
    ax.invert_yaxis()
    ax.set_xlim(0, 1.12)
    ax.legend(frameon=False, fontsize=9, loc="lower right", labelcolor=TEXT_SECONDARY)
    fig.tight_layout()
    path = folder / "test_comparison.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path, stats


def fmt(value):
    return "n/a" if value is None else f"{value:.3f}"


def write_report(summary, rows, stats, charts, folder: Path) -> Path:
    config = summary.get("config", {})
    lines = [
        f"# Experiment {summary['experiment_run']}",
        "",
        "Generated by `evaluation/plot_results.py` from `queries.csv` and `summary.json`. Every number below is "
        "computed from stored query records; nothing is entered by hand.",
        "",
        "## Configuration",
        "",
        *[f"- **{key}:** {value}" for key, value in config.items()],
        "",
        "## Mean scores per cycle",
        "",
        "| cycle | phase | mode | n | precision | relevance | groundedness | citation acc. | answer rel. | "
        "coverage | overall | latency (s) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in summary["cycles"]:
        m = c["means"]
        latency = c["mean_latency_ms"] / 1000 if c["mean_latency_ms"] else None
        lines.append(
            f"| {c['cycle'] + 1 if c['phase'] == 'train' else 'test'} | {c['phase']} | {c['mode']} | "
            f"{c['evaluated']} | {fmt(m['retrieval_precision'])} | {fmt(m['retrieval_relevance'])} | "
            f"{fmt(m['groundedness'])} | {fmt(m['citation_accuracy'])} | {fmt(m['answer_relevance'])} | "
            f"{fmt(m['evidence_coverage'])} | {fmt(m['overall'])} | {fmt(latency)} |"
        )
    lines += ["", "## Ranking weights at the end of each cycle", "", "| after | α | β | γ |", "|---|---|---|---|"]
    test_cycles = {c["cycle"] for c in summary["cycles"] if c["phase"] == "test"}
    for w in summary["weights"]:
        if w["cycle"] < 0:
            label = "start"
        elif w["cycle"] in test_cycles:
            label = "test (frozen)"
        else:
            label = f"cycle {w['cycle'] + 1}"
        lines.append(f"| {label} | {w['alpha']:.3f} | {w['beta']:.3f} | {w['gamma']:.3f} |")
    if summary.get("retrieval_change"):
        lines += ["", "## Retrieval change between cycles", "", "| cycles | mean top-k Jaccard | questions |",
                  "|---|---|---|"]
        for change in summary["retrieval_change"]:
            lines.append(f"| {change['cycle']} → {change['cycle'] + 1} | "
                         f"{change['mean_topk_jaccard_vs_previous']:.3f} | {change['questions']} |")
    if stats:
        lines += ["", "## Held-out paraphrases (paired, learning frozen)", "",
                  "| metric | baseline | proposed | mean diff | 95% bootstrap CI | wins / losses |",
                  "|---|---|---|---|---|---|"]
        for key, s in stats.items():
            ci = f"[{s['ci95'][0]:+.3f}, {s['ci95'][1]:+.3f}]" if s["ci95"] else "n/a"
            lines.append(f"| {key} | {s['baseline']:.3f} | {s['proposed']:.3f} | {s['difference']:+.3f} | {ci} | "
                         f"{s['wins']} / {s['losses']} of {s['pairs']} |")
    failed = [r for r in rows if r["status"] != "completed"]
    lines += ["", "## Run health", "", f"- **Queries:** {len(rows)}", f"- **Failed:** {len(failed)}",
              f"- **Evaluation errors:** {sum(1 for r in rows if (r['error'] or '').startswith('evaluation failed'))}"]
    lines += ["", "## Charts", "", *[f"![{p.stem}]({p.name})" for p in charts if p]]
    path = folder / "report.md"
    path.write_text("\n".join(lines) + "\n")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot charts and a report for one experiment run.")
    parser.add_argument("run_id")
    parser.add_argument("--results", type=Path, default=ROOT / "evaluation" / "results")
    args = parser.parse_args()
    folder = args.results / args.run_id
    summary, rows = load(folder)
    test_chart, stats = plot_test_comparison(rows, folder)
    charts = [
        plot_metrics_by_cycle(summary, folder),
        plot_weights(rows, summary, folder),
        plot_retrieval_change(summary, folder),
        test_chart,
        plot_latency(rows, folder),
    ]
    (folder / "test_stats.json").write_text(json.dumps(stats, indent=2))
    print(write_report(summary, rows, stats, charts, folder))


if __name__ == "__main__":
    main()
