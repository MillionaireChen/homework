#!/usr/bin/env python3
"""Validate final summary-evaluation JSON or JSONL output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


MAXIMA = {
    "faithfulness": 50,
    "coverage": 30,
    "coherence": 15,
    "conciseness": 5,
}
TERMINAL_RANKS = {
    "OFF_TOPIC": 0,
    "EMPTY_OUTPUT": 0,
    "VERBATIM_SOURCE_COPY": 1,
    "OBVIOUS_TRUNCATION": 2,
    "OVER_SENTENCE_LIMIT": 3,
}


def load(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if path.suffix.lower() == ".jsonl":
        return [
            json.loads(line) for line in text.splitlines() if line.strip()
        ]
    value = json.loads(text)
    return value if isinstance(value, list) else [value]


def validate(item: Dict[str, Any], index: int) -> List[str]:
    errors: List[str] = []
    prefix = "record {}".format(index)
    score = item.get("score")
    if (
        not isinstance(score, (int, float))
        or isinstance(score, bool)
        or not 0 <= score <= 100
    ):
        errors.append("{}: score must be numeric in 0..100".format(prefix))
    if not isinstance(item.get("quality_label"), str):
        errors.append("{}: quality_label is required".format(prefix))
    trace = item.get("evaluation_trace")
    if not isinstance(trace, list) or not trace:
        errors.append("{}: non-empty evaluation_trace is required".format(prefix))
    review = item.get("review")
    if not isinstance(review, dict) or review.get("decision") not in {
        "APPROVE", "ESCALATE"
    }:
        errors.append(
            "{}: final review decision must be APPROVE or ESCALATE".format(prefix)
        )

    eligible = item.get("eligible_for_soft_scoring") is True
    if not eligible:
        terminal = item.get("terminal_result")
        if terminal not in TERMINAL_RANKS:
            errors.append("{}: terminal_result is missing or invalid".format(prefix))
        if score != 0:
            errors.append("{}: terminal result must score 0".format(prefix))
        expected_rank = TERMINAL_RANKS.get(terminal)
        if item.get("terminal_rank") != expected_rank:
            errors.append(
                "{}: terminal_rank must be {} for {}".format(
                    prefix, expected_rank, terminal
                )
            )
        if item.get("dimensions") is not None:
            errors.append("{}: terminal dimensions must be null".format(prefix))
        if isinstance(review, dict) and review.get("decision") != "APPROVE":
            errors.append("{}: terminal result requires Reviewer approval".format(prefix))
        if not isinstance(trace, list) or not any(
            event.get("stage") == "early_stop" for event in trace
        ):
            errors.append("{}: terminal result needs early_stop trace".format(prefix))
    else:
        if item.get("terminal_rank") is not None:
            errors.append("{}: eligible result terminal_rank must be null".format(prefix))
        dimensions = item.get("dimensions")
        if not isinstance(dimensions, dict):
            errors.append("{}: dimensions required for soft score".format(prefix))
        else:
            total = 0.0
            for name, maximum in MAXIMA.items():
                value = dimensions.get(name)
                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not 0 <= value <= maximum
                ):
                    errors.append(
                        "{}: {} must be numeric in 0..{}".format(
                            prefix, name, maximum
                        )
                    )
                else:
                    total += value
            if isinstance(score, (int, float)) and abs(total - score) > 1e-6:
                errors.append(
                    "{}: dimensions sum to {}, not score {}".format(
                        prefix, total, score
                    )
                )

    if "reference_summary" in json.dumps(item, ensure_ascii=False):
        errors.append("{}: reference_summary is forbidden".format(prefix))
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    errors: List[str] = []
    for index, item in enumerate(load(args.input), start=1):
        errors.extend(validate(item, index))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    print("valid: {}".format(args.input))


if __name__ == "__main__":
    main()
