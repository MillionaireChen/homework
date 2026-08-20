#!/usr/bin/env python3
"""Apply Reviewer decisions on Grounding Gate proposals to produce terminals and survivors.

The physical gates run first and catch what a string test can prove. This stage is the
semantic hard constraint and the last line of defence before scoring: a candidate that
is unrelated to its article, asserts the opposite of it, or invents its central content
never reaches soft scoring. A confirmed proposal stops at score 0; a rejected proposal
continues to the Scorer with both positions recorded in the trace.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


TERMINAL_META = {
    "OFF_TOPIC": "HARD_FAIL_OFF_TOPIC",
    "FACTUAL_REVERSAL": "HARD_FAIL_REVERSAL",
    "FABRICATED_CONTENT": "HARD_FAIL_FABRICATION",
}


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, required=True, help="survivors handed to the gate")
    parser.add_argument("--gate", type=Path, required=True, help="validated Grounding Gate output")
    parser.add_argument("--reviews", type=Path, required=True, help="Reviewer grounding decisions")
    parser.add_argument("--survivors-output", type=Path, required=True)
    parser.add_argument("--terminals-output", type=Path, required=True)
    args = parser.parse_args()

    pairs = read_jsonl(args.pairs)
    gate = {str(row["summary_id"]): row for row in read_jsonl(args.gate)}
    review_rows = read_jsonl(args.reviews)
    reviews = {str(row["summary_id"]): row for row in review_rows}

    if set(gate) != {str(row["summary_id"]) for row in pairs}:
        raise ValueError("every supplied pair needs exactly one gate judgment")
    proposed = {
        summary_id
        for summary_id, row in gate.items()
        if row.get("verdict") == "NOT_GROUNDED"
    }
    if len(reviews) != len(review_rows) or set(reviews) != proposed:
        raise ValueError("review IDs must match the gate's NOT_GROUNDED IDs exactly")

    survivors: List[Dict[str, Any]] = []
    terminals: List[Dict[str, Any]] = []
    for pair in pairs:
        summary_id = str(pair["summary_id"])
        judgment = gate[summary_id]
        trace = list(pair.get("evaluation_trace", []))
        trace.append(
            {
                "stage": "grounding_gate",
                "result": judgment["verdict"],
                "evidence": {
                    "category": judgment.get("category"),
                    "article_evidence": judgment.get("article_evidence", []),
                    "candidate_evidence": judgment.get("candidate_evidence", []),
                    "findings": judgment.get("findings", []),
                },
            }
        )
        if judgment["verdict"] == "GROUNDED":
            survivor = dict(pair)
            survivor["evaluation_trace"] = trace
            survivors.append(survivor)
            continue

        category = judgment.get("category")
        if category not in TERMINAL_META:
            raise ValueError(f"unknown grounding category for {summary_id}: {category}")
        review = reviews[summary_id]
        decision = review.get("decision")
        findings = list(review.get("findings", []))
        trace.append(
            {
                "stage": "grounding_review",
                "result": decision,
                "evidence": {"confidence": review.get("confidence"), "findings": findings},
            }
        )
        if decision == "REJECT":
            # The gate over-reached. Scoring continues and the trace keeps both positions.
            survivor = dict(pair)
            survivor["evaluation_trace"] = trace
            survivors.append(survivor)
            continue
        if decision != "APPROVE":
            raise ValueError(f"invalid grounding review decision for {summary_id}: {decision}")

        trace.append(
            {
                "stage": "early_stop",
                "result": category,
                "evidence": {"skipped_stages": ["anchor_generation", "soft_scoring"]},
            }
        )
        terminals.append(
            {
                "article_id": pair["article_id"],
                "summary_id": summary_id,
                "eligible_for_soft_scoring": False,
                "score": 0,
                "terminal_result": category,
                "terminal_rank": 0,
                "quality_label": TERMINAL_META[category],
                "hard_fail": True,
                "hard_fail_reason": category,
                "dimensions": None,
                "anchor": None,
                "claim_checks": judgment.get("claim_checks", []),
                "issues": findings or list(judgment.get("findings", [])),
                "source_evidence": list(judgment.get("article_evidence", [])),
                "few_shot_used": category,
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
    confirmed = len(terminals)
    rejected = len(proposed) - confirmed
    print(
        f"gate proposals: {len(proposed)}; confirmed terminal: {confirmed}; "
        f"rejected and continued: {rejected}; soft-scoring survivors: {len(survivors)}"
    )


if __name__ == "__main__":
    main()
