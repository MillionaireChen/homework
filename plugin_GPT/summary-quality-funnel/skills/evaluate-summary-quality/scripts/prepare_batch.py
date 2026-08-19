#!/usr/bin/env python3
"""Join article and summary JSONL without copying reference summaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--articles", type=Path, required=True)
    parser.add_argument("--summaries", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--article-corpus-output", type=Path, required=True)
    args = parser.parse_args()

    articles = {str(row["article_id"]): row for row in read_jsonl(args.articles)}
    summaries = read_jsonl(args.summaries)
    inputs = []
    for row in summaries:
        article_id = str(row["article_id"])
        article = articles[article_id]
        inputs.append(
            {
                "article_id": article_id,
                "summary_id": str(row["summary_id"]),
                "title": article.get("title", ""),
                "article": article["text"],
                "summary": row["summary"],
            }
        )
    corpus = [
        {
            "article_id": article_id,
            "title": article.get("title", ""),
            "article": article["text"],
        }
        for article_id, article in articles.items()
    ]
    write_jsonl(args.output, inputs)
    write_jsonl(args.article_corpus_output, corpus)
    print(f"prepared {len(inputs)} pairs from {len(corpus)} articles; reference summaries excluded")


if __name__ == "__main__":
    main()
