#!/usr/bin/env python3
"""Convert the plugin-ranked JSONL result into the requested JSON array."""

from __future__ import annotations

import json
from pathlib import Path


root = Path(__file__).resolve().parent
rows = [
    json.loads(line)
    for line in (root / "score_ranked.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
(root / "score.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
