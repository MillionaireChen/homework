#!/usr/bin/env python3
"""Validate the final Reviewer pass after the one allowed score revision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revisions", type=Path, required=True)
    parser.add_argument("--final-reviews", type=Path, required=True)
    args = parser.parse_args()
    revisions = read_jsonl(args.revisions)
    reviews = read_jsonl(args.final_reviews)
    errors = []
    if [str(row.get("summary_id")) for row in reviews] != [str(row.get("summary_id")) for row in revisions]:
        errors.append("final-review IDs/order do not match revised drafts")
    for index, row in enumerate(reviews, start=1):
        prefix = f"record {index}"
        if row.get("decision") not in {"APPROVE", "ESCALATE"}:
            errors.append(f"{prefix}: final decision must be APPROVE or ESCALATE")
        if row.get("confidence") not in {"HIGH", "MEDIUM", "LOW"}:
            errors.append(f"{prefix}: invalid confidence")
        if not isinstance(row.get("findings"), list):
            errors.append(f"{prefix}: findings must be a list")
        if not isinstance(row.get("few_shot_used"), str) or not row.get("few_shot_used"):
            errors.append(f"{prefix}: few_shot_used is required")
        event = row.get("review_trace_event")
        if not isinstance(event, dict) or event.get("stage") != "final_score_review":
            errors.append(f"{prefix}: final_score_review trace event is required")
        elif event.get("result") != row.get("decision"):
            errors.append(f"{prefix}: trace decision mismatch")
        if "reference_summary" in json.dumps(row, ensure_ascii=False):
            errors.append(f"{prefix}: reference summary is forbidden")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"valid final reviews: {len(reviews)}")


if __name__ == "__main__":
    main()
