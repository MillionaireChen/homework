#!/usr/bin/env python3
"""Add Ollama embedding relevance evidence to surviving article-summary pairs.

A production request carries one article and one candidate, so a candidate is only
ever compared with its own assigned article. Comparing it with any other article
uses context the caller never supplied, which the business rule forbids: no
own-article rank, no best-match article, no margin against other articles.

The similarity is a weak nomination signal, never terminal. An independent semantic
Reviewer decides whether the candidate is genuinely unrelated, and a confirmed
off-topic candidate receives score 0.
"""

from __future__ import annotations

import argparse
import json
import math
import urllib.request
from pathlib import Path
from typing import Any, Dict, List


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def ollama_embed(
    texts: List[str], endpoint: str, model: str, batch_size: int
) -> List[List[float]]:
    vectors: List[List[float]] = []
    for start in range(0, len(texts), batch_size):
        payload = json.dumps({
            "model": model, "input": texts[start : start + batch_size]
        }).encode("utf-8")
        request = urllib.request.Request(
            endpoint, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=600) as response:
            body = json.loads(response.read().decode("utf-8"))
            vectors.extend(body["embeddings"])
    return vectors


def cosine(left: List[float], right: List[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    return dot / (norm_left * norm_right) if norm_left and norm_right else 0.0


def article_representation(item: Dict[str, Any], maximum_chars: int) -> str:
    body = item.get("article", item.get("text"))
    if body is None:
        raise ValueError("article rows need article or text")
    title = str(item.get("title", "")).strip()
    clipped = str(body)[:maximum_chars]
    return "{}\n{}".format(title, clipped) if title else clipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, required=True,
        help="JSONL; each row needs article_id, article, and summary",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="qwen3-embedding:0.6b")
    parser.add_argument(
        "--endpoint", default="http://127.0.0.1:11434/api/embed"
    )
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument(
        "--article-max-chars", type=int, default=1500,
        help="article body characters used for embedding; 1500 matches calibration",
    )
    parser.add_argument(
        "--absolute-threshold", type=float, default=0.50,
        help="assigned similarity below this value becomes an off-topic suspect",
    )
    args = parser.parse_args()

    rows = [row for row in read_jsonl(args.input) if not row.get("hard_fail")]
    if not rows:
        args.output.write_text("", encoding="utf-8")
        return

    # One vector per assigned article. Reuse within a batch is a cost saving only:
    # each candidate is scored against its own article and nothing else.
    article_by_id: Dict[str, str] = {}
    for index, row in enumerate(rows):
        article_id = str(row.get("article_id", "article_{}".format(index)))
        row["article_id"] = article_id
        article_by_id.setdefault(
            article_id, article_representation(row, args.article_max_chars)
        )
    article_ids = list(article_by_id)
    article_vectors = dict(
        zip(
            article_ids,
            ollama_embed(
                [article_by_id[item] for item in article_ids],
                args.endpoint,
                args.model,
                args.batch_size,
            ),
        )
    )
    summary_vectors = ollama_embed(
        [str(row["summary"]) for row in rows],
        args.endpoint,
        args.model,
        args.batch_size,
    )

    outputs: List[Dict[str, Any]] = []
    for row, vector in zip(rows, summary_vectors):
        similarity = cosine(vector, article_vectors[str(row["article_id"])])
        suspect = similarity < args.absolute_threshold
        evidence = {
            "model": args.model,
            "mode": "assigned_article_only",
            "assigned_similarity": round(similarity, 4),
            "absolute_threshold": args.absolute_threshold,
            "off_topic_suspect": suspect,
            "requires_independent_confirmation": suspect,
            "comparisons_against_other_articles": 0,
        }
        output = dict(row)
        output["embedding_evidence"] = evidence
        output.setdefault("evaluation_trace", []).append({
            "stage": "embedding_relevance",
            "result": "SUSPECT" if suspect else "PASS_OR_WEAK_SIGNAL",
            "evidence": evidence,
        })
        outputs.append(output)

    args.output.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in outputs) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
