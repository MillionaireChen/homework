#!/usr/bin/env python3
"""Generate a fixed-format Markdown report, statistics, and charts deterministically."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from make_report_charts import build_stats, load_rows, plot_outcomes, plot_scores
from validate_report import validate_report


TERMINAL_LABELS = {
    "EMPTY_OUTPUT": "empty output",
    "OFF_TOPIC": "off-topic",
    "VERBATIM_SOURCE_COPY": "verbatim source copy",
    "OBVIOUS_TRUNCATION": "obvious truncation",
    "OVER_SENTENCE_LIMIT": "over the sentence limit",
}
TERMINAL_ORDER = [
    "VERBATIM_SOURCE_COPY",
    "OBVIOUS_TRUNCATION",
    "OFF_TOPIC",
    "OVER_SENTENCE_LIMIT",
    "EMPTY_OUTPUT",
]
LABEL_ORDER = ["EXCELLENT", "GOOD", "MIXED", "POOR"]


def load_optional_json(path: Path | None) -> Dict[str, Any] | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"optional JSON input must contain one object: {path}")
    return value


def load_conclusion(path: Path) -> str:
    conclusion = path.read_text(encoding="utf-8").strip()
    if not conclusion:
        raise ValueError("conclusion input is empty")
    if re.search(r"^#{1,6}\s", conclusion, flags=re.M):
        raise ValueError("conclusion input must not contain Markdown headings")
    if "![" in conclusion or "```" in conclusion:
        raise ValueError("conclusion input must not contain images or code fences")
    words = re.findall(r"[A-Za-z0-9]+(?:[._%+\-/][A-Za-z0-9]+)*", conclusion)
    if len(words) > 120:
        raise ValueError(f"conclusion has {len(words)} lexical units; maximum is 120")
    return conclusion


def number(value: Any, digits: int = 2) -> str:
    if value is None:
        return "not available"
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.{digits}f}".rstrip("0").rstrip(".")


def list_counts(counts: Dict[str, Any], order: List[str], labels: Dict[str, str] | None = None) -> str:
    labels = labels or {}
    keys = [key for key in order if int(counts.get(key, 0)) > 0]
    keys += sorted(key for key in counts if key not in order and int(counts[key]) > 0)
    if not keys:
        return "none"
    return ", ".join(f"{int(counts[key])} {labels.get(key, key)}" for key in keys)


def relative_markdown_path(target: Path, report: Path) -> str:
    return Path(os.path.relpath(target, start=report.parent)).as_posix()


def ablation_paragraph(ablation: Dict[str, Any] | None) -> str:
    if not ablation:
        return ""
    try:
        coverage = ablation["correlations"]["coverage"]
        article_spearman = coverage["article_embedding"]["spearman"]
        anchor_spearman = coverage["anchor_embedding"]["spearman"]
        loocv = ablation["coverage_prediction_loocv"]
        article_mae = loocv["article_only"]["mae"]
        anchor_mae = loocv["anchor_only"]["mae"]
        combined_mae = loocv["article_plus_anchor"]["mae"]
    except (KeyError, TypeError) as exc:
        raise ValueError("ablation input does not match the expected schema") from exc

    best = min(
        [(article_mae, "article similarity alone"), (anchor_mae, "anchor similarity alone"), (combined_mae, "both features")],
        key=lambda item: (float(item[0]), item[1]),
    )[1]
    return (
        "\n\nThe optional embedding ablation reported coverage Spearman correlations of "
        f"{number(article_spearman, 4)} for article similarity and {number(anchor_spearman, 4)} "
        f"for anchor similarity. Leave-one-out coverage MAE was {number(article_mae, 4)} for article "
        f"similarity, {number(anchor_mae, 4)} for anchor similarity, and {number(combined_mae, 4)} for "
        f"both features; the lowest error came from {best}. These deterministic results do not establish "
        "a stable predictive gain from anchor embeddings."
    )


def render_report(
    rows: List[Dict[str, Any]],
    stats: Dict[str, Any],
    score_input: Path,
    report_output: Path,
    outcomes_chart: Path,
    scores_chart: Path,
    ablation: Dict[str, Any] | None,
    conclusion: str,
) -> str:
    input_stats = stats["input"]
    funnel = stats["funnel"]
    soft = stats["soft_scores"]
    review = stats["review"]
    terminal_text = list_counts(funnel["terminal_by_type"], TERMINAL_ORDER, TERMINAL_LABELS)
    label_text = list_counts(soft["labels"], LABEL_ORDER)
    approved_without_revision = max(0, int(review["approved"]) - int(review["revised_at_least_once"]))
    eligible = sorted(
        (row for row in rows if row.get("eligible_for_soft_scoring") is True),
        key=lambda row: (float(row["score"]), str(row.get("summary_id"))),
    )
    score_extremes = "No candidates qualified for soft scoring."
    if eligible:
        lowest, highest = eligible[0], eligible[-1]
        score_extremes = (
            f"The highest soft score was {number(highest['score'])} for `{highest.get('summary_id')}`; "
            f"the lowest was {number(lowest['score'])} for `{lowest.get('summary_id')}`."
        )

    routing_details = ""
    if input_stats.get("hard_gate_artifact_supplied"):
        routing_details += (
            f" The deterministic gate proposed {funnel['deterministic_gate_proposals']} terminal outcomes, "
            f"and downstream review recovered {funnel['hard_failures_recovered_downstream']} additional hard failures."
        )
    if input_stats.get("embedding_artifact_supplied"):
        routing_details += (
            f" Embedding evidence nominated {funnel['embedding_off_topic_suspects']} off-topic suspects; "
            f"the Reviewer confirmed {funnel['embedding_off_topic_confirmed']} and rejected "
            f"{funnel['embedding_suspects_rejected']}. Embedding evidence alone was not terminal."
        )

    outcome_rel = relative_markdown_path(outcomes_chart, report_output)
    score_rel = relative_markdown_path(scores_chart, report_output)
    dimensions = soft["dimension_means"]

    return f"""# Summary Quality Evaluation Report

## 1. Input Data

The validated input file `{score_input.name}` contains {input_stats['pairs']} Japanese news article-summary pairs from {input_stats['unique_articles']} unique articles. Runtime scoring did not use reference summaries.

## 2. Funnel Outcomes

{funnel['fully_soft_scored']} pairs completed soft scoring and {funnel['terminal_total']} stopped early. Terminal outcomes were {terminal_text}.{routing_details}

![Pipeline outcomes]({outcome_rel})

## 3. Results

The {soft['count']} soft scores had a mean of {number(soft['mean'])}, a median of {number(soft['median'])}, and a range of {number(soft['minimum'])}–{number(soft['maximum'])}. The label distribution was {label_text}. Mean dimension scores were {number(dimensions['faithfulness'])}/50 for faithfulness, {number(dimensions['coverage'])}/30 for coverage, {number(dimensions['coherence'])}/15 for coherence, and {number(dimensions['conciseness'])}/5 for conciseness.

The Reviewer approved {review['approved']} of {input_stats['pairs']} final records. {approved_without_revision} were approved without revision, {review['revised_at_least_once']} required at least one revision, and {review['escalated']} remained escalated. {score_extremes}{ablation_paragraph(ablation)}

![Reviewer-approved soft scores]({score_rel})

## 4. Conclusion

{conclusion}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="validated final score JSON or JSONL")
    parser.add_argument("--report-output", type=Path, required=True, help="Markdown report path")
    parser.add_argument("--asset-dir", type=Path, required=True, help="directory for statistics and PNG charts")
    parser.add_argument("--hard-gate-input", type=Path)
    parser.add_argument("--embedding-input", type=Path)
    parser.add_argument("--ablation-input", type=Path, help="optional audited anchor-embedding ablation JSON")
    parser.add_argument("--conclusion-input", type=Path, required=True, help="Report Agent conclusion text; 120 words maximum")
    parser.add_argument("--max-words", type=int, default=800)
    args = parser.parse_args()

    rows = load_rows(args.input)
    hard_rows = load_rows(args.hard_gate_input) if args.hard_gate_input else []
    embedding_rows = load_rows(args.embedding_input) if args.embedding_input else []
    ablation = load_optional_json(args.ablation_input)
    conclusion = load_conclusion(args.conclusion_input)

    args.asset_dir.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    stats = build_stats(rows, hard_rows, embedding_rows)
    stats_output = args.asset_dir / "report_stats.json"
    outcomes_chart = args.asset_dir / "pipeline_outcomes.png"
    scores_chart = args.asset_dir / "soft_score_results.png"
    stats_output.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plot_outcomes(stats, outcomes_chart)
    plot_scores(rows, scores_chart)
    report = render_report(
        rows,
        stats,
        args.input,
        args.report_output,
        outcomes_chart,
        scores_chart,
        ablation,
        conclusion,
    )
    args.report_output.write_text(report, encoding="utf-8")
    units = validate_report(args.report_output, args.max_words)

    print(f"report: {args.report_output}")
    print(f"stats: {stats_output}")
    print(f"chart: {outcomes_chart}")
    print(f"chart: {scores_chart}")
    print(f"validation: passed ({units}/{args.max_words} lexical units)")


if __name__ == "__main__":
    main()
