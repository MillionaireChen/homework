#!/usr/bin/env python3
"""Validate Grounding Gate Agent output before any review or scoring runs.

The gate is the semantic hard constraint. It answers one question per candidate:
is this text grounded in the supplied article at all? It never scores quality, so a
row carrying dimensions or a score is rejected here rather than downstream.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


VERDICTS = {"GROUNDED", "NOT_GROUNDED"}
CATEGORIES = {"OFF_TOPIC", "FACTUAL_REVERSAL", "FABRICATED_CONTENT"}
FORBIDDEN_KEYS = {"score", "dimensions", "quality_label", "faithfulness", "coverage"}


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, required=True, help="survivors handed to the gate")
    parser.add_argument("--gate", type=Path, required=True, help="Grounding Gate Agent output")
    args = parser.parse_args()

    pairs = read_jsonl(args.pairs)
    gate = read_jsonl(args.gate)
    expected = [str(row["summary_id"]) for row in pairs]
    actual = [str(row.get("summary_id")) for row in gate]
    errors: List[str] = []

    if actual != expected:
        errors.append("gate IDs or order do not match the supplied pairs exactly")

    for index, row in enumerate(gate, start=1):
        summary_id = row.get("summary_id", f"row {index}")
        verdict = row.get("verdict")
        if verdict not in VERDICTS:
            errors.append(f"{summary_id}: verdict must be one of {sorted(VERDICTS)}")
            continue
        leaked = sorted(FORBIDDEN_KEYS & set(row))
        if leaked:
            errors.append(f"{summary_id}: the gate must not score; remove {leaked}")
        if verdict == "GROUNDED":
            if row.get("category") not in (None, ""):
                errors.append(f"{summary_id}: GROUNDED rows carry no category")
            continue
        if row.get("category") not in CATEGORIES:
            errors.append(f"{summary_id}: category must be one of {sorted(CATEGORIES)}")
        article_spans = row.get("article_evidence") or []
        candidate_spans = row.get("candidate_evidence") or []
        if not article_spans or not candidate_spans:
            errors.append(
                f"{summary_id}: NOT_GROUNDED needs at least one article span and one candidate span"
            )
        if not (row.get("findings") or []):
            errors.append(f"{summary_id}: NOT_GROUNDED needs at least one finding")

    if errors:
        raise SystemExit("\n".join(errors))
    proposals = sum(1 for row in gate if row.get("verdict") == "NOT_GROUNDED")
    print(f"valid gate output: {len(gate)} judged, {proposals} proposed NOT_GROUNDED")


if __name__ == "__main__":
    main()
