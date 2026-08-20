#!/usr/bin/env python3
"""Apply approved soft-score reviews and isolate one-pass revision requests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drafts", type=Path, nargs="+", required=True)
    parser.add_argument("--reviews", type=Path, nargs="+", required=True)
    parser.add_argument("--approved-output", type=Path, required=True)
    parser.add_argument("--revision-output", type=Path, required=True)
    args = parser.parse_args()

    drafts = [row for path in args.drafts for row in read_jsonl(path)]
    reviews = [row for path in args.reviews for row in read_jsonl(path)]
    review_by_id = {str(row["summary_id"]): row for row in reviews}
    if len(review_by_id) != len(reviews):
        raise SystemExit("duplicate summary_id in reviews")
    if {str(row["summary_id"]) for row in drafts} != set(review_by_id):
        raise SystemExit("draft and review summary IDs differ")

    approved = []
    revisions = []
    for draft in drafts:
        review = review_by_id[str(draft["summary_id"])]
        if review["decision"] == "APPROVE":
            final = dict(draft)
            final.pop("draft_status", None)
            final["terminal_rank"] = None
            final["hard_fail"] = False
            final["hard_fail_reason"] = None
            final["terminal_result"] = None
            final["review"] = {
                "decision": "APPROVE",
                "rounds": 1,
                "confidence": review["confidence"],
                "findings": review["findings"],
            }
            final["evaluation_trace"] = list(final.get("evaluation_trace", [])) + [review["review_trace_event"]]
            approved.append(final)
        else:
            revisions.append({"scorer_draft": draft, "review": review})

    write_jsonl(args.approved_output, approved)
    write_jsonl(args.revision_output, revisions)
    print(f"approved={len(approved)} revision_or_escalation={len(revisions)}")


if __name__ == "__main__":
    main()
