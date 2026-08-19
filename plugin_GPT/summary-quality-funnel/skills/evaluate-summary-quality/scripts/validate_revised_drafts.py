#!/usr/bin/env python3
"""Validate the Scorer's single revision pass against Reviewer requests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


MAXIMA = {"faithfulness": 50, "coverage": 30, "coherence": 15, "conciseness": 5}


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def label(score: float) -> str:
    return "EXCELLENT" if score >= 90 else "GOOD" if score >= 75 else "MIXED" if score >= 50 else "POOR"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--revisions", type=Path, required=True)
    args = parser.parse_args()
    reviews = read_jsonl(args.reviews)
    revisions = read_jsonl(args.revisions)
    expected_ids = [str(row["summary_id"]) for row in reviews if row.get("decision") == "REVISE"]
    actual_ids = [str(row.get("summary_id")) for row in revisions]
    errors = []
    if actual_ids != expected_ids:
        errors.append("revision IDs/order do not match REVISE requests")
    for index, row in enumerate(revisions, start=1):
        prefix = f"record {index}"
        dimensions = row.get("dimensions")
        if not isinstance(dimensions, dict):
            errors.append(f"{prefix}: dimensions missing")
            continue
        total = 0
        for name, maximum in MAXIMA.items():
            value = dimensions.get(name)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= maximum:
                errors.append(f"{prefix}: invalid {name}")
            else:
                total += value
        if row.get("score") != total:
            errors.append(f"{prefix}: score does not equal dimension sum")
        if row.get("quality_label") != label(total):
            errors.append(f"{prefix}: quality label does not match score")
        if not isinstance(row.get("revision_notes"), list) or not row.get("revision_notes"):
            errors.append(f"{prefix}: revision_notes are required")
        events = [event for event in row.get("evaluation_trace", []) if event.get("stage") == "score_revision"]
        if len(events) != 1:
            errors.append(f"{prefix}: exactly one score_revision trace event is required")
        if "reference_summary" in json.dumps(row, ensure_ascii=False):
            errors.append(f"{prefix}: reference summary is forbidden")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"valid revised drafts: {len(revisions)}")


if __name__ == "__main__":
    main()
