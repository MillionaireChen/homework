#!/usr/bin/env python3
"""Apply Codex Reviewer hard-gate decisions to draft JSONL deterministically."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


TERMINAL_RANKS = {
    "EMPTY_OUTPUT": 0,
    "VERBATIM_SOURCE_COPY": 1,
    "OBVIOUS_TRUNCATION": 2,
    "OVER_SENTENCE_LIMIT": 3,
}
TERMINAL_LABELS = {
    "EMPTY_OUTPUT": "HARD_FAIL_EMPTY",
    "VERBATIM_SOURCE_COPY": "HARD_FAIL_COPY",
    "OBVIOUS_TRUNCATION": "HARD_FAIL_TRUNCATION",
    "OVER_SENTENCE_LIMIT": "HARD_FAIL_OVER_LENGTH",
}


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
    proposal_ids = [str(row["summary_id"]) for row in drafts if row.get("draft_terminal_result")]
    if len(reviews) != len(review_rows) or set(reviews) != set(proposal_ids):
        raise ValueError("review IDs must match hard-gate proposal IDs exactly")

    survivors = []
    terminals = []
    for draft in drafts:
        summary_id = str(draft["summary_id"])
        terminal = draft.get("draft_terminal_result")
        if not terminal:
            survivors.append(draft)
            continue
        review = reviews[summary_id]
        trace = list(draft.get("evaluation_trace", []))
        trace.append(
            {
                "stage": "terminal_review",
                "result": review["decision"],
                "evidence": {
                    "confidence": review.get("confidence"),
                    "findings": review.get("findings", []),
                },
            }
        )
        if review["decision"] == "REJECT":
            continued = dict(draft)
            continued.update(
                {
                    "status": "READY_FOR_RELEVANCE",
                    "eligible_for_soft_scoring": None,
                    "draft_score": None,
                    "draft_terminal_result": None,
                    "terminal_rank": None,
                    "hard_fail": False,
                    "evaluation_trace": trace,
                }
            )
            survivors.append(continued)
            continue
        if review["decision"] != "APPROVE":
            raise ValueError(f"invalid hard review decision for {summary_id}: {review['decision']}")
        findings = list(review.get("findings", []))
        trace.append(
            {
                "stage": "early_stop",
                "result": terminal,
                "evidence": {
                    "skipped_stages": ["embedding_relevance", "anchor_generation", "soft_scoring"],
                },
            }
        )
        terminals.append(
            {
                "article_id": draft["article_id"],
                "summary_id": summary_id,
                "eligible_for_soft_scoring": False,
                "score": 0,
                "terminal_result": terminal,
                "terminal_rank": TERMINAL_RANKS[terminal],
                "quality_label": TERMINAL_LABELS[terminal],
                "hard_fail": True,
                "hard_fail_reason": terminal,
                "dimensions": None,
                "anchor": None,
                "claim_checks": [],
                "issues": findings,
                "source_evidence": [],
                "few_shot_used": terminal,
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
    print(f"approved terminal results: {len(terminals)}; survivors: {len(survivors)}")


if __name__ == "__main__":
    main()
