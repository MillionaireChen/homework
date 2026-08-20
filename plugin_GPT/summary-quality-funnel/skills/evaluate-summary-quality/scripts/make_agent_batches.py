#!/usr/bin/env python3
"""Split survivor JSONL into deterministic article-aligned Agent batches."""

from __future__ import annotations

import argparse
import json
from collections import OrderedDict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--articles-per-batch", type=int, default=5)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    groups = OrderedDict()
    for row in rows:
        groups.setdefault(str(row["article_id"]), []).append(row)
    article_ids = list(groups)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for start in range(0, len(article_ids), args.articles_per_batch):
        selected = article_ids[start : start + args.articles_per_batch]
        batch_rows = [row for article_id in selected for row in groups[article_id]]
        batch_number = len(manifest) + 1
        path = args.output_dir / f"batch_{batch_number:02d}.jsonl"
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in batch_rows), encoding="utf-8")
        manifest.append({"batch": batch_number, "file": path.name, "article_ids": selected, "pairs": len(batch_rows)})
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"created {len(manifest)} batches for {len(article_ids)} articles and {len(rows)} pairs")


if __name__ == "__main__":
    main()
