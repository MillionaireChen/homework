#!/usr/bin/env python3
"""Create deterministic report statistics and charts from final score JSON/JSONL."""

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
    embedding_suspects = sum(
        bool(row.get("embedding_evidence", {}).get("off_topic_suspect"))
        for row in embedding_rows
    )
    return {
        "input": {
            "pairs": len(rows),
            "unique_articles": len({str(row.get("article_id")) for row in rows}),
            "reference_summary_used": False,
        },
        "funnel": {
            "fully_soft_scored": len(eligible),
            "terminal_total": len(terminal),
            "terminal_by_type": dict(sorted(terminal_counts.items())),
            "deterministic_gate_proposals": len(deterministic_ids),
            "hard_failures_recovered_downstream": len(final_hard_ids - deterministic_ids),
            "embedding_off_topic_suspects": embedding_suspects,
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
            "revised_at_least_once": sum(int(row.get("review", {}).get("rounds", 0)) > 1 for row in rows),
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
    eligible = sorted(
        (row for row in rows if row.get("eligible_for_soft_scoring") is True),
        key=lambda row: (float(row["score"]), str(row.get("summary_id"))),
        reverse=True,
    )
    scores = [float(row["score"]) for row in eligible]
    colors = [LABEL_COLORS.get(row.get("quality_label"), "#6C757D") for row in eligible]
    labels = [f"S{index}" for index in range(1, len(eligible) + 1)]
    mean = statistics.fmean(scores) if scores else 0.0

    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    bars = ax.bar(labels, scores, color=colors, width=0.72)
    ax.axhline(mean, color="#264653", linestyle="--", linewidth=1.4, label=f"Mean {mean:.1f}")
    for bar, value in zip(bars, scores):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 1.2, f"{value:.0f}", ha="center", fontsize=8)
    ax.set_title("Reviewer-approved soft scores", loc="left", fontsize=15, fontweight="bold")
    ax.set_ylabel("Score (0–100)")
    ax.set_ylim(0, 108)
    ax.grid(axis="y", alpha=0.18)
    ax.legend(frameon=False, loc="lower left")
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
