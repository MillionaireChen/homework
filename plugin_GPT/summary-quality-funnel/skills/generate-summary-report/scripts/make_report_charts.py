#!/usr/bin/env python3
"""Create deterministic report statistics and charts from final score JSON/JSONL.

This module is used by generate_report.py. Its CLI remains available for chart-only
diagnostics, but the Report Agent must call generate_report.py for final reports.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "summary-quality-report-mpl")
)
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


OUTCOME_ORDER = [
    ("SOFT_SCORED", "Soft scored", "#2E86AB"),
    ("VERBATIM_SOURCE_COPY", "Source copy", "#D1495B"),
    ("OBVIOUS_TRUNCATION", "Truncated", "#F4A261"),
    ("OFF_TOPIC", "Off-topic", "#6C757D"),
    ("OVER_SENTENCE_LIMIT", "Over length", "#8E6C8A"),
    ("EMPTY_OUTPUT", "Empty", "#ADB5BD"),
]
LABEL_COLORS = {
    "EXCELLENT": "#2A9D8F",
    "GOOD": "#4C956C",
    "MIXED": "#E9C46A",
    "POOR": "#E76F51",
}


def load_rows(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    value = json.loads(text)
    return value if isinstance(value, list) else [value]


def round_or_none(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def build_stats(
    rows: List[Dict[str, Any]],
    hard_rows: List[Dict[str, Any]],
    embedding_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not rows:
        raise ValueError("score input is empty")
    eligible = [row for row in rows if row.get("eligible_for_soft_scoring") is True]
    terminal = [row for row in rows if row.get("eligible_for_soft_scoring") is not True]
    terminal_counts = Counter(row.get("terminal_result", "UNKNOWN") for row in terminal)
    label_counts = Counter(row.get("quality_label", "UNKNOWN") for row in eligible)
    scores = [float(row["score"]) for row in eligible]
    dimension_names = ["faithfulness", "coverage", "coherence", "conciseness"]
    dimension_means = {
        name: round_or_none(
            statistics.fmean(float(row["dimensions"][name]) for row in eligible)
        )
        if eligible
        else None
        for name in dimension_names
    }
    hard_by_id = {row.get("summary_id"): row for row in hard_rows}
    final_hard_ids = {
        row.get("summary_id")
        for row in terminal
        if row.get("terminal_result")
        in {"EMPTY_OUTPUT", "VERBATIM_SOURCE_COPY", "OBVIOUS_TRUNCATION", "OVER_SENTENCE_LIMIT"}
    }
    deterministic_ids = {
        row.get("summary_id")
        for row in hard_rows
        if row.get("draft_terminal_result")
    }
    embedding_suspect_ids = {
        row.get("summary_id")
        for row in embedding_rows
        if row.get("embedding_evidence", {}).get("off_topic_suspect")
    }
    confirmed_off_topic_ids = {
        row.get("summary_id")
        for row in terminal
        if row.get("terminal_result") == "OFF_TOPIC"
    }
    return {
        "input": {
            "pairs": len(rows),
            "unique_articles": len({str(row.get("article_id")) for row in rows}),
            "reference_summary_used": False,
            "hard_gate_artifact_supplied": bool(hard_rows),
            "embedding_artifact_supplied": bool(embedding_rows),
        },
        "funnel": {
            "fully_soft_scored": len(eligible),
            "terminal_total": len(terminal),
            "terminal_by_type": dict(sorted(terminal_counts.items())),
            "deterministic_gate_proposals": len(deterministic_ids),
            "hard_failures_recovered_downstream": len(final_hard_ids - deterministic_ids),
            "embedding_off_topic_suspects": len(embedding_suspect_ids),
            "embedding_off_topic_confirmed": len(embedding_suspect_ids & confirmed_off_topic_ids),
            "embedding_suspects_rejected": len(embedding_suspect_ids - confirmed_off_topic_ids),
        },
        "soft_scores": {
            "count": len(eligible),
            "mean": round_or_none(statistics.fmean(scores)) if scores else None,
            "median": round_or_none(statistics.median(scores)) if scores else None,
            "minimum": round_or_none(min(scores)) if scores else None,
            "maximum": round_or_none(max(scores)) if scores else None,
            "labels": dict(sorted(label_counts.items())),
            "dimension_means": dimension_means,
        },
        "review": {
            "approved": sum(row.get("review", {}).get("decision") == "APPROVE" for row in rows),
            "escalated": sum(row.get("review", {}).get("decision") == "ESCALATE" for row in rows),
            "revised_at_least_once": sum(
                any(event.get("stage") == "score_revision" for event in row.get("evaluation_trace", []))
                for row in rows
            ),
        },
    }


def plot_outcomes(stats: Dict[str, Any], output: Path) -> None:
    terminal = stats["funnel"]["terminal_by_type"]
    values = {
        "SOFT_SCORED": stats["funnel"]["fully_soft_scored"],
        **terminal,
    }
    selected = [(key, label, color, values.get(key, 0)) for key, label, color in OUTCOME_ORDER]
    selected = [item for item in selected if item[3] > 0]
    labels = [item[1] for item in selected]
    counts = [item[3] for item in selected]
    colors = [item[2] for item in selected]

    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    bars = ax.barh(labels[::-1], counts[::-1], color=colors[::-1], height=0.62)
    total = stats["input"]["pairs"]
    for bar, count in zip(bars, counts[::-1]):
        ax.text(
            bar.get_width() + 0.18,
            bar.get_y() + bar.get_height() / 2,
            f"{count}  ({count / total:.0%})",
            va="center",
            fontsize=10,
        )
    ax.set_title("Pipeline outcomes", loc="left", fontsize=15, fontweight="bold")
    ax.set_xlabel("Article-summary pairs")
    ax.set_xlim(0, max(counts) * 1.28)
    ax.grid(axis="x", alpha=0.18)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_scores(rows: List[Dict[str, Any]], output: Path) -> None:
    eligible = [row for row in rows if row.get("eligible_for_soft_scoring") is True]
    scores = [float(row["score"]) for row in eligible]
    mean = statistics.fmean(scores) if scores else 0.0
    median = statistics.median(scores) if scores else 0.0
    label_counts = Counter(row.get("quality_label", "UNKNOWN") for row in eligible)

    fig, (score_ax, label_ax) = plt.subplots(
        1, 2, figsize=(9.2, 4.8), gridspec_kw={"width_ratios": [2.15, 1]}
    )
    bins = list(range(0, 101, 10))
    score_ax.hist(scores, bins=bins, color="#2E86AB", edgecolor="white", linewidth=1.0)
    score_ax.axvline(mean, color="#264653", linestyle="--", linewidth=1.5, label=f"Mean {mean:.1f}")
    score_ax.axvline(median, color="#E76F51", linestyle=":", linewidth=1.7, label=f"Median {median:.1f}")
    score_ax.set_title("Soft-score distribution", loc="left", fontsize=14, fontweight="bold")
    score_ax.set_xlabel("Score (0–100)")
    score_ax.set_ylabel("Candidates")
    score_ax.set_xlim(0, 100)
    score_ax.grid(axis="y", alpha=0.18)
    score_ax.legend(frameon=False)

    label_order = [name for name in ("EXCELLENT", "GOOD", "MIXED", "POOR") if label_counts.get(name)]
    label_values = [label_counts[name] for name in label_order]
    bars = label_ax.barh(
        label_order[::-1],
        label_values[::-1],
        color=[LABEL_COLORS[name] for name in label_order[::-1]],
        height=0.58,
    )
    for bar, value in zip(bars, label_values[::-1]):
        label_ax.text(bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2, str(value), va="center")
    label_ax.set_title("Quality labels", loc="left", fontsize=14, fontweight="bold")
    label_ax.set_xlabel("Candidates")
    label_ax.set_xlim(0, max(label_values, default=1) * 1.25)
    label_ax.grid(axis="x", alpha=0.18)
    for ax in (score_ax, label_ax):
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="final score JSON or JSONL")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--stats-output", type=Path)
    parser.add_argument("--hard-gate-input", type=Path)
    parser.add_argument("--embedding-input", type=Path)
    args = parser.parse_args()

    rows = load_rows(args.input)
    hard_rows = load_rows(args.hard_gate_input) if args.hard_gate_input else []
    embedding_rows = load_rows(args.embedding_input) if args.embedding_input else []
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stats = build_stats(rows, hard_rows, embedding_rows)
    stats_output = args.stats_output or args.output_dir / "report_stats.json"
    stats_output.parent.mkdir(parents=True, exist_ok=True)
    stats_output.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    plot_outcomes(stats, args.output_dir / "pipeline_outcomes.png")
    plot_scores(rows, args.output_dir / "soft_score_results.png")
    print(f"stats: {stats_output}")
    print(f"chart: {args.output_dir / 'pipeline_outcomes.png'}")
    print(f"chart: {args.output_dir / 'soft_score_results.png'}")


if __name__ == "__main__":
    main()
