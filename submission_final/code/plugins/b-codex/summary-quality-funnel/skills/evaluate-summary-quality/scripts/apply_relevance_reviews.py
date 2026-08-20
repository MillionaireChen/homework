#!/usr/bin/env python3
"""Apply Codex Reviewer relevance decisions to embedding draft JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drafts", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--survivors-output", type=Path, required=True)
    parser.add_argument("--terminals-output", type=Path, required=True)
    args = parser.parse_args()

    drafts = read_jsonl(args.drafts)
    review_rows = read_jsonl(args.reviews)
    reviews = {str(row["summary_id"]): row for row in review_rows}
    suspect_ids = [
        str(row["summary_id"])
        for row in drafts
        if row.get("embedding_evidence", {}).get("off_topic_suspect") is True
    ]
    if len(reviews) != len(review_rows) or set(reviews) != set(suspect_ids):
        raise ValueError("review IDs must match embedding suspect IDs exactly")

    survivors = []
    terminals = []
    for draft in drafts:
        summary_id = str(draft["summary_id"])
        evidence = draft.get("embedding_evidence", {})
        if not evidence.get("off_topic_suspect"):
            survivors.append(draft)
            continue
        review = reviews[summary_id]
        trace = list(draft.get("evaluation_trace", []))
        trace.append(
            {
                "stage": "relevance_review",
                "result": review["decision"],
                "evidence": {
                    "confidence": review.get("confidence"),
                    "findings": review.get("findings", []),
                },
            }
        )
        if review["decision"] == "REJECT":
            continued = dict(draft)
            continued["evaluation_trace"] = trace
            survivors.append(continued)
            continue
        if review["decision"] != "APPROVE":
            raise ValueError(f"invalid relevance review decision for {summary_id}: {review['decision']}")
        findings = list(review.get("findings", []))
        trace.append(
            {
                "stage": "early_stop",
                "result": "OFF_TOPIC",
                "evidence": {"skipped_stages": ["anchor_generation", "soft_scoring"]},
            }
        )
        terminals.append(
            {
                "article_id": draft["article_id"],
                "summary_id": summary_id,
                "eligible_for_soft_scoring": False,
                "score": 0,
                "terminal_result": "OFF_TOPIC",
                "terminal_rank": 0,
                "quality_label": "HARD_FAIL_OFF_TOPIC",
                "hard_fail": True,
                "hard_fail_reason": "OFF_TOPIC",
                "dimensions": None,
                "anchor": None,
                "claim_checks": [],
                "issues": findings,
                "source_evidence": [],
                "few_shot_used": "OFF_TOPIC",
                "review": {
                    "decision": "APPROVE",
                    "rounds": 1,
                    "confidence": review.get("confidence", "HIGH"),
                    "findings": findings,
                },
                "evaluation_trace": trace,
            }
        )

    write_jsonl(args.survivors_output, survivors)
    write_jsonl(args.terminals_output, terminals)
    print(f"confirmed off-topic: {len(terminals)}; soft-scoring survivors: {len(survivors)}")


if __name__ == "__main__":
    main()
