#!/usr/bin/env python3
"""Offline reference cross-check for a finished evaluation run.

Reference summaries are forbidden at every runtime stage. They are read here, in the
report stage only, to build a weak ground truth that the evaluator never saw, so a
reader can judge detection accuracy instead of trusting unlabelled counts.

Planted categories are derived from the corpus alone. The score file is joined only
afterwards, so no evaluator output can influence a label.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import tempfile
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "summary-quality-report-mpl")
)
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


NEAR_REFERENCE_RATIO = 0.90

# Planted categories whose correct outcome is a terminal result with score 0.
PLANTED_BAD = ["COPY_OF_ARTICLE", "TRUNCATED_REFERENCE", "OFF_TOPIC"]
# The one category whose correct outcome is a surviving soft score.
PLANTED_GOOD = "REFERENCE_VERBATIM"
UNLABELLED = "GENERATED_UNKNOWN"
CATEGORY_ORDER = [PLANTED_GOOD] + PLANTED_BAD + [UNLABELLED]
CATEGORY_TEXT = {
    "REFERENCE_VERBATIM": "reference summary reproduced verbatim",
    "COPY_OF_ARTICLE": "continuous copy of the source article",
    "TRUNCATED_REFERENCE": "leading fragment of the reference summary",
    "OFF_TOPIC": "unrelated to its assigned article",
    "GENERATED_UNKNOWN": "generated candidate with no derivable label",
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text or ""))


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    value = json.loads(text)
    return value if isinstance(value, list) else [value]


def classify(candidate: str, article_id: str, texts: Dict[str, str], refs: Dict[str, str]) -> str:
    """Label one candidate using only the supplied corpus.

    The last branch scans the rest of the corpus purely to establish, offline, that a
    candidate is unrelated to its own article. The runtime taxonomy has one such
    category, OFF_TOPIC, and no runtime stage may compare a candidate with any article
    other than its own.
    """
    cand = normalize(candidate)
    own_text, own_ref = texts[article_id], refs[article_id]
    if cand and cand in own_text:
        return "COPY_OF_ARTICLE"
    if cand and cand == own_ref:
        return "REFERENCE_VERBATIM"
    if cand and own_ref.startswith(cand):
        return "TRUNCATED_REFERENCE"
    for other_id, other_ref in refs.items():
        if other_id == article_id or not cand:
            continue
        if (
            cand in texts[other_id]
            or cand == other_ref
            or SequenceMatcher(None, cand, other_ref).ratio() >= NEAR_REFERENCE_RATIO
        ):
            return "OFF_TOPIC"
    return UNLABELLED


def score_summary(scores: List[float]) -> Dict[str, Any] | None:
    if not scores:
        return None
    ordered = sorted(scores)
    return {
        "count": len(ordered),
        "mean": round(statistics.fmean(ordered), 2),
        "median": round(statistics.median(ordered), 2),
        "minimum": ordered[0],
        "maximum": ordered[-1],
    }


def build_reference_stats(
    articles: List[Dict[str, Any]],
    summaries: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    texts = {str(a["article_id"]): normalize(a["text"]) for a in articles}
    refs = {str(a["article_id"]): normalize(a["reference_summary"]) for a in articles}
    by_id = {str(row.get("summary_id")): row for row in rows}

    labelled: List[Dict[str, Any]] = []
    for item in summaries:
        summary_id = str(item["summary_id"])
        row = by_id.get(summary_id)
        if row is None:
            continue
        labelled.append(
            {
                "summary_id": summary_id,
                "article_id": str(item["article_id"]),
                "planted_category": classify(
                    item["summary"], str(item["article_id"]), texts, refs
                ),
                "score": float(row.get("score", 0.0)),
                "quality_label": row.get("quality_label"),
                "terminal_result": row.get("terminal_result"),
            }
        )
    if not labelled:
        raise ValueError("no summary in the corpus matched a scored record")

    categories: Dict[str, Any] = {}
    for name in CATEGORY_ORDER:
        members = [item for item in labelled if item["planted_category"] == name]
        if not members:
            continue
        rejected = [item for item in members if item["score"] == 0.0]
        survived = [item for item in members if item["score"] > 0.0]
        expected_terminal = name in PLANTED_BAD
        correct = rejected if expected_terminal else survived
        entry: Dict[str, Any] = {
            "description": CATEGORY_TEXT[name],
            "count": len(members),
            "expected_outcome": "terminal"
            if expected_terminal
            else ("surviving soft score" if name == PLANTED_GOOD else "not labelled"),
            "rejected_with_zero": len(rejected),
            "surviving_soft_scores": score_summary([item["score"] for item in survived]),
            "labels": dict(Counter(item["quality_label"] for item in survived)),
        }
        if name != UNLABELLED:
            entry["correct"] = len(correct)
            entry["detection_rate"] = round(len(correct) / len(members), 4)
            entry["disagreements"] = [
                {
                    "summary_id": item["summary_id"],
                    "score": item["score"],
                    "quality_label": item["quality_label"],
                }
                for item in members
                if item not in correct
            ]
        categories[name] = entry

    graded = [item for item in labelled if item["planted_category"] != UNLABELLED]
    correct_total = sum(
        1
        for item in graded
        if (item["score"] == 0.0) == (item["planted_category"] in PLANTED_BAD)
    )

    by_article: Dict[str, List[Dict[str, Any]]] = {}
    for item in labelled:
        by_article.setdefault(item["article_id"], []).append(item)
    comparable = 0
    inversions = []
    for article_id, members in sorted(by_article.items()):
        good = [m["score"] for m in members if m["planted_category"] == PLANTED_GOOD]
        bad = [m["score"] for m in members if m["planted_category"] in PLANTED_BAD]
        if not good or not bad:
            continue
        comparable += 1
        if max(bad) >= min(good):
            inversions.append(article_id)

    return {
        "provenance": {
            "reference_summary_used_at_runtime": False,
            "reference_summary_read_at_report_stage": True,
            "labelling_inputs": "articles and summaries corpus only",
            "near_reference_ratio": NEAR_REFERENCE_RATIO,
        },
        "corpus": {
            "scored_records": len(rows),
            "labelled_records": len(labelled),
            "gradable_records": len(graded),
            "unlabelled_records": len(labelled) - len(graded),
        },
        "categories": categories,
        "accuracy": {
            "gradable_records": len(graded),
            "correct": correct_total,
            "rate": round(correct_total / len(graded), 4) if graded else None,
        },
        "within_article_ordering": {
            "comparable_articles": comparable,
            "articles_with_planted_bad_at_or_above_reference": len(inversions),
            "inverted_articles": inversions,
        },
    }


def plot_reference_validation(stats: Dict[str, Any], output: Path) -> Path:
    categories = stats["categories"]
    names = [name for name in CATEGORY_ORDER if name in categories and name != UNLABELLED]
    correct = [categories[name]["correct"] for name in names]
    missed = [categories[name]["count"] - categories[name]["correct"] for name in names]
    labels = [name.replace("_", " ").title() for name in names]

    figure, axes = plt.subplots(figsize=(8.0, 4.2))
    positions = list(range(len(names)))
    axes.bar(positions, correct, color="#2A9D8F", label="Outcome matched the planted category")
    axes.bar(positions, missed, bottom=correct, color="#E76F51", label="Disagreed")
    for index, (right, wrong) in enumerate(zip(correct, missed)):
        axes.text(index, right + wrong + 0.6, f"{right}/{right + wrong}", ha="center", fontsize=10)
    tallest = max((r + w for r, w in zip(correct, missed)), default=1)
    axes.set_ylim(0, tallest * 1.18)
    axes.set_xticks(positions)
    axes.set_xticklabels(labels, fontsize=9)
    axes.set_ylabel("Candidates")
    axes.set_title("Offline reference cross-check (evaluator never saw references)")
    axes.legend(fontsize=9)
    axes.spines["top"].set_visible(False)
    axes.spines["right"].set_visible(False)
    figure.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=150)
    plt.close(figure)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="validated final score JSON or JSONL")
    parser.add_argument("--articles", type=Path, required=True, help="corpus articles JSONL")
    parser.add_argument("--summaries", type=Path, required=True, help="corpus summaries JSONL")
    parser.add_argument("--output", type=Path, required=True, help="reference_validation.json path")
    parser.add_argument("--chart-output", type=Path, help="optional PNG path")
    args = parser.parse_args()

    stats = build_reference_stats(
        load_jsonl(args.articles), load_jsonl(args.summaries), load_jsonl(args.input)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"reference validation: {args.output}")
    if args.chart_output:
        print(f"chart: {plot_reference_validation(stats, args.chart_output)}")


if __name__ == "__main__":
    main()
