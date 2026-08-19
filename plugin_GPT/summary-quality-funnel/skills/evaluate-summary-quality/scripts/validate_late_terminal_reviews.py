#!/usr/bin/env python3
"""Validate Reviewer-confirmed terminal failures discovered during soft review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


TERMINALS = {
    "EMPTY_OUTPUT",
    "OFF_TOPIC",
    "VERBATIM_SOURCE_COPY",
    "OBVIOUS_TRUNCATION",
    "OVER_SENTENCE_LIMIT",
}


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soft-reviews", type=Path, required=True)
    parser.add_argument("--terminal-reviews", type=Path, required=True)
    args = parser.parse_args()
    soft = read_jsonl(args.soft_reviews)
    terminal = read_jsonl(args.terminal_reviews)
    expected = [str(row["summary_id"]) for row in soft if row.get("decision") == "ESCALATE"]
    actual = [str(row.get("summary_id")) for row in terminal]
    errors = []
    if actual != expected:
        errors.append("late terminal IDs/order do not match ESCALATE soft reviews")
    for index, row in enumerate(terminal, start=1):
        prefix = f"record {index}"
        if row.get("proposed_terminal_result") not in TERMINALS:
            errors.append(f"{prefix}: invalid proposed_terminal_result")
        if row.get("decision") not in {"APPROVE", "REJECT"}:
            errors.append(f"{prefix}: decision must be APPROVE or REJECT")
        if row.get("confidence") not in {"HIGH", "MEDIUM", "LOW"}:
            errors.append(f"{prefix}: invalid confidence")
        if not isinstance(row.get("findings"), list) or not row.get("findings"):
            errors.append(f"{prefix}: findings are required")
        if not isinstance(row.get("few_shot_used"), str) or not row.get("few_shot_used"):
            errors.append(f"{prefix}: few_shot_used is required")
        event = row.get("review_trace_event") or row.get("terminal_review_trace_event")
        if not isinstance(event, dict) or event.get("stage") != "terminal_review":
            errors.append(f"{prefix}: terminal_review trace event is required")
        if "reference_summary" in json.dumps(row, ensure_ascii=False):
            errors.append(f"{prefix}: reference summary is forbidden")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"valid late terminal reviews: {len(terminal)}")


if __name__ == "__main__":
    main()
