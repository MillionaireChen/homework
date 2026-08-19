#!/usr/bin/env python3
"""Validate independent Codex Reviewer JSONL against a scoring batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


MAXIMA = {"faithfulness": 50, "coverage": 30, "coherence": 15, "conciseness": 5}
DECISIONS = {"APPROVE", "REVISE", "ESCALATE"}
CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-batch", type=Path, required=True)
    parser.add_argument("--drafts", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    args = parser.parse_args()

    inputs = read_jsonl(args.input_batch)
    drafts = read_jsonl(args.drafts)
    reviews = read_jsonl(args.reviews)
    expected_ids = [str(row["summary_id"]) for row in inputs]
    errors = []
    if [str(row.get("summary_id")) for row in drafts] != expected_ids:
        errors.append("scorer draft IDs/order do not match the input batch")
    if [str(row.get("summary_id")) for row in reviews] != expected_ids:
        errors.append("review IDs/order do not match the input batch")

    for index, row in enumerate(reviews, start=1):
        prefix = f"record {index}"
        if row.get("decision") not in DECISIONS:
            errors.append(f"{prefix}: invalid decision")
        if row.get("confidence") not in CONFIDENCE:
            errors.append(f"{prefix}: invalid confidence")
        if not isinstance(row.get("findings"), list):
            errors.append(f"{prefix}: findings must be a list")
        if not isinstance(row.get("few_shot_used"), str) or not row.get("few_shot_used"):
            errors.append(f"{prefix}: few_shot_used is required")
        event = row.get("review_trace_event")
        if not isinstance(event, dict) or event.get("stage") != "soft_score_review":
            errors.append(f"{prefix}: soft_score_review trace event is required")
        elif event.get("result") != row.get("decision"):
            errors.append(f"{prefix}: trace decision mismatch")

        if row.get("decision") == "REVISE":
            dimensions = row.get("suggested_dimensions")
            if not isinstance(dimensions, dict):
                errors.append(f"{prefix}: REVISE requires suggested_dimensions")
                continue
            total = 0
            for name, maximum in MAXIMA.items():
                value = dimensions.get(name)
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= maximum:
                    errors.append(f"{prefix}: invalid suggested {name}")
                else:
                    total += value
            if row.get("suggested_score") != total:
                errors.append(f"{prefix}: suggested_score does not equal dimension sum")
        elif row.get("suggested_dimensions") is not None or row.get("suggested_score") is not None:
            errors.append(f"{prefix}: non-REVISE review must not suggest scores")

        if "reference_summary" in json.dumps(row, ensure_ascii=False):
            errors.append(f"{prefix}: reference summary is forbidden")

    if errors:
        raise SystemExit("\n".join(errors))
    counts = {decision: sum(row["decision"] == decision for row in reviews) for decision in sorted(DECISIONS)}
    print(f"valid reviewer output: {len(reviews)} records; decisions={counts}")


if __name__ == "__main__":
    main()
