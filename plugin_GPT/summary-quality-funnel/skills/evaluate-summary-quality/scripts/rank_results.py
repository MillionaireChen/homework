#!/usr/bin/env python3
"""Rank validated summary results within each article."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


def ranking_key(item: Dict[str, Any]) -> Tuple[int, float]:
    if item.get("eligible_for_soft_scoring") is True:
        return (1, float(item["score"]))
    return (0, float(item.get("terminal_rank", 0)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [
        json.loads(line)
        for line in args.input.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get("article_id", "__single__"))].append(row)
    output: List[Dict[str, Any]] = []
    for article_id, group in groups.items():
        ordered = sorted(group, key=ranking_key, reverse=True)
        previous_key = None
        previous_rank = 0
        for position, row in enumerate(ordered, start=1):
            key = ranking_key(row)
            rank = previous_rank if key == previous_key else position
            row = dict(row)
            row["rank_within_article"] = rank
            output.append(row)
            previous_key = key
            previous_rank = rank
    args.output.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in output) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
