#!/usr/bin/env python3
"""Validate Codex Scorer draft JSONL against its source batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


MAXIMA = {"faithfulness": 50, "coverage": 30, "coherence": 15, "conciseness": 5}


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def expected_label(score: float) -> str:
    if score >= 90:
        return "EXCELLENT"
    if score >= 75:
        return "GOOD"
    if score >= 50:
        return "MIXED"
    return "POOR"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-batch", type=Path, required=True)
    parser.add_argument("--drafts", type=Path, required=True)
    args = parser.parse_args()
    inputs = read_jsonl(args.input_batch)
    drafts = read_jsonl(args.drafts)
    expected_ids = [str(row["summary_id"]) for row in inputs]
    actual_ids = [str(row.get("summary_id")) for row in drafts]
    errors = []
    if actual_ids != expected_ids:
        errors.append("draft summary IDs/order do not match the input batch")
    anchors = {}
    for index, row in enumerate(drafts, start=1):
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
        if row.get("quality_label") != expected_label(total):
            errors.append(f"{prefix}: quality label does not match score")
        if row.get("eligible_for_soft_scoring") is not True:
            errors.append(f"{prefix}: draft must be eligible")
        if not isinstance(row.get("claim_checks"), list):
            errors.append(f"{prefix}: claim_checks must be a list")
        article_id = str(row.get("article_id"))
        anchor = row.get("anchor")
        if not isinstance(anchor, dict):
            errors.append(f"{prefix}: anchor missing")
        elif article_id in anchors and anchors[article_id] != anchor:
            errors.append(f"{prefix}: anchor differs within one article")
        else:
            anchors[article_id] = anchor
        stages = [event.get("stage") for event in row.get("evaluation_trace", [])]
        if "anchor_generation" not in stages or "draft_scoring" not in stages:
            errors.append(f"{prefix}: required trace stages missing")
        if "reference_summary" in json.dumps(row, ensure_ascii=False):
            errors.append(f"{prefix}: reference summary is forbidden")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"valid scorer drafts: {len(drafts)} records across {len(anchors)} articles")


if __name__ == "__main__":
    main()
