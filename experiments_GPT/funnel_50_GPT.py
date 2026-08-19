#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Small, reference-free funnel probe for 50 candidate summaries.

The production-facing inputs are deliberately limited to:
  * article title + body
  * candidate summary

`reference_summary` is never read or used.

Stage 1: deterministic verbatim-copy detection against the assigned body.
Stage 2: embedding retrieval over all 50 article bodies.
Stage 3: reranker confirmation for summaries whose assigned article loses
         clearly to another article.

The script tests the first 10 articles (5 summaries each = 50 summaries) by
default. It writes only new files whose names end in ``_GPT``.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import numpy as np
from sentence_transformers import CrossEncoder, SentenceTransformer


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTICLES = ROOT / "data" / "articles.jsonl"
DEFAULT_SUMMARIES = ROOT / "data" / "summaries.jsonl"
DEFAULT_OUTPUT = Path(__file__).with_name("funnel_50_results_GPT.json")
DEFAULT_REPORT = Path(__file__).with_name("funnel_50_report_GPT.md")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def normalize_exact(text: str) -> str:
    """Normalize harmless presentation differences without paraphrasing."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def shingle_coverage(summary: str, source: str, width: int = 12) -> float:
    if len(summary) < width:
        return float(summary in source)
    shingles = [summary[i : i + width] for i in range(len(summary) - width + 1)]
    return sum(shingle in source for shingle in shingles) / len(shingles)


def copy_features(summary: str, source: str) -> Dict[str, Any]:
    """Measure only literal overlap; semantic similarity is handled later."""
    candidate = normalize_exact(summary)
    body = normalize_exact(source)
    matcher = difflib.SequenceMatcher(None, candidate, body, autojunk=False)
    blocks = matcher.get_matching_blocks()
    longest = max((block.size for block in blocks), default=0)
    matched = sum(block.size for block in blocks)
    length = max(len(candidate), 1)
    shingles = shingle_coverage(candidate, body)
    full_containment = len(candidate) >= 30 and candidate in body

    # Conservative rules for literal copying. Thresholds are intentionally
    # exposed in the output and should be calibrated before production use.
    is_copy = bool(
        full_containment
        or (longest >= 50 and longest / length >= 0.50)
        or (longest >= 30 and shingles >= 0.85)
    )
    return {
        "normalized_chars": len(candidate),
        "full_containment": full_containment,
        "longest_exact_chars": longest,
        "longest_exact_ratio": round(longest / length, 4),
        "matched_char_ratio": round(min(matched / length, 1.0), 4),
        "shingle12_coverage": round(shingles, 4),
        "copy_reject": is_copy,
    }


def article_for_embedding(article: Dict[str, Any]) -> str:
    # No reference field is touched here.
    return f"{article['title']}\n{article['text'][:1500]}"


def article_for_reranker(article: Dict[str, Any]) -> str:
    # Keep the most topical opening section within the cross-encoder context.
    return f"{article['title']}\n{article['text'][:1000]}"


def encode(
    model: SentenceTransformer, texts: Sequence[str], batch_size: int
) -> np.ndarray:
    vectors = model.encode(
        list(texts),
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return np.asarray(vectors, dtype=np.float32)


def choose_test_summaries(
    articles: Sequence[Dict[str, Any]],
    summaries: Sequence[Dict[str, Any]],
    summary_limit: int,
) -> List[Dict[str, Any]]:
    if summary_limit <= 0 or summary_limit % 5:
        raise ValueError("--summary-limit must be a positive multiple of 5")
    article_count = summary_limit // 5
    selected_ids = {article["article_id"] for article in articles[:article_count]}
    selected = [s for s in summaries if s["article_id"] in selected_ids]
    if len(selected) != summary_limit:
        raise ValueError(
            f"expected {summary_limit} summaries for the first {article_count} "
            f"articles, found {len(selected)}"
        )
    return selected


def rerank_candidates(
    model: CrossEncoder,
    rows: List[Dict[str, Any]],
    articles: Sequence[Dict[str, Any]],
    article_index: Dict[str, int],
    shortlist_size: int,
    batch_size: int,
) -> None:
    """Score all non-copy pilot rows so embedding/reranker disagreements stay visible."""
    pairs: List[List[str]] = []
    jobs: List[tuple[Dict[str, Any], List[int]]] = []

    for row in rows:
        if row["copy"]["copy_reject"]:
            continue
        own_idx = article_index[row["article_id"]]
        order = row.pop("_embedding_order")
        best_other_idx = next(int(idx) for idx in order if int(idx) != own_idx)
        # Rerank the assigned article plus the strongest embedding alternatives.
        candidate_indices = [own_idx]
        for idx in order:
            idx = int(idx)
            if idx not in candidate_indices:
                candidate_indices.append(idx)
            if len(candidate_indices) >= shortlist_size + 1:
                break
        if best_other_idx not in candidate_indices:
            candidate_indices.append(best_other_idx)

        jobs.append((row, candidate_indices))
        for idx in candidate_indices:
            pairs.append([row["summary"], article_for_reranker(articles[idx])])

    if not pairs:
        return

    scores = model.predict(pairs, batch_size=batch_size, show_progress_bar=True)
    cursor = 0
    for row, candidate_indices in jobs:
        count = len(candidate_indices)
        candidate_scores = [float(x) for x in scores[cursor : cursor + count]]
        cursor += count
        scored = sorted(
            zip(candidate_indices, candidate_scores), key=lambda pair: pair[1], reverse=True
        )
        own_idx = article_index[row["article_id"]]
        own_score = next(score for idx, score in scored if idx == own_idx)
        best_idx, best_score = scored[0]
        best_other_score = max(score for idx, score in scored if idx != own_idx)
        margin = own_score - best_other_score

        # A hard rejection needs agreement from both retrieval stages.
        embedding_suspect = (
            row["embedding"]["own_rank"] > 1
            and row["embedding"]["margin_vs_best_other"] <= -0.10
        )
        reranker_confirms = (
            best_idx != own_idx and own_score <= 0.20 and margin <= -0.50
        )
        row["reranker"] = {
            "assigned_score": round(own_score, 4),
            "best_match_article_id": articles[best_idx]["article_id"],
            "best_match_title": articles[best_idx]["title"],
            "best_match_score": round(best_score, 4),
            "margin_vs_best_other": round(margin, 4),
            "embedding_suspect": embedding_suspect,
            "reranker_confirms": reranker_confirms,
            "scored_candidates": [
                {
                    "article_id": articles[idx]["article_id"],
                    "score": round(score, 4),
                }
                for idx, score in scored
            ],
        }
        row["decision"] = (
            "OFFTOPIC_REJECT"
            if embedding_suspect and reranker_confirms
            else "PASS_TO_SEMANTIC"
        )


def write_report(
    path: Path,
    payload: Dict[str, Any],
    articles_by_id: Dict[str, Dict[str, Any]],
) -> None:
    rows = payload["results"]
    counts = Counter(row["decision"] for row in rows)
    lines = [
        "# 50-summary funnel probe (GPT)",
        "",
        "This is a small, reference-free test. `reference_summary` was not read or used.",
        "",
        "## Outcome",
        "",
        f"- Tested summaries: {len(rows)}",
        f"- `COPY_REJECT`: {counts['COPY_REJECT']}",
        f"- `OFFTOPIC_REJECT`: {counts['OFFTOPIC_REJECT']}",
        f"- `PASS_TO_SEMANTIC`: {counts['PASS_TO_SEMANTIC']}",
        "",
        "## Rejected summaries",
        "",
        "| decision | summary_id | assigned article | strongest matched article | evidence |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        if row["decision"] == "PASS_TO_SEMANTIC":
            continue
        assigned = articles_by_id[row["article_id"]]["title"].replace("|", "｜")
        if row["decision"] == "COPY_REJECT":
            best = "—"
            evidence = (
                f"full={row['copy']['full_containment']}; "
                f"longest={row['copy']['longest_exact_chars']} chars; "
                f"shingle12={row['copy']['shingle12_coverage']:.3f}"
            )
        else:
            best = row["reranker"]["best_match_title"].replace("|", "｜")
            evidence = (
                f"emb rank={row['embedding']['own_rank']}, "
                f"margin={row['embedding']['margin_vs_best_other']:+.3f}; "
                f"rerank margin={row['reranker']['margin_vs_best_other']:+.3f}"
            )
        lines.append(
            f"| {row['decision']} | `{row['summary_id']}` | {assigned} | {best} | {evidence} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This funnel only removes obvious failures. A passed summary is not automatically good; "
            "it still needs faithfulness, coverage, completeness, and fluency evaluation.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--articles", type=Path, default=DEFAULT_ARTICLES)
    parser.add_argument("--summaries", type=Path, default=DEFAULT_SUMMARIES)
    parser.add_argument("--summary-limit", type=int, default=50)
    parser.add_argument("--embedding-model", default="BAAI/bge-m3")
    parser.add_argument("--reranker-model", default="BAAI/bge-reranker-v2-m3")
    parser.add_argument("--shortlist-size", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    articles = read_jsonl(args.articles)
    summaries = read_jsonl(args.summaries)
    test_summaries = choose_test_summaries(articles, summaries, args.summary_limit)
    articles_by_id = {article["article_id"]: article for article in articles}
    article_index = {article["article_id"]: i for i, article in enumerate(articles)}

    rows: List[Dict[str, Any]] = []
    for summary in test_summaries:
        article = articles_by_id[summary["article_id"]]
        copy = copy_features(summary["summary"], article["text"])
        rows.append(
            {
                "summary_id": summary["summary_id"],
                "article_id": summary["article_id"],
                "summary": summary["summary"],
                "copy": copy,
                "decision": "COPY_REJECT" if copy["copy_reject"] else "PENDING",
            }
        )

    print(f"Loading embedding model: {args.embedding_model}")
    embedding_model = SentenceTransformer(
        args.embedding_model, local_files_only=True, device="cpu"
    )
    article_vectors = encode(
        embedding_model,
        [article_for_embedding(article) for article in articles],
        args.batch_size,
    )
    summary_vectors = encode(
        embedding_model,
        [row["summary"] for row in rows],
        args.batch_size,
    )
    similarities = summary_vectors @ article_vectors.T

    for row, scores in zip(rows, similarities):
        own_idx = article_index[row["article_id"]]
        order = np.argsort(-scores)
        own_rank = int(np.where(order == own_idx)[0][0]) + 1
        best_other_idx = next(int(idx) for idx in order if int(idx) != own_idx)
        margin = float(scores[own_idx] - scores[best_other_idx])
        row["embedding"] = {
            "assigned_similarity": round(float(scores[own_idx]), 4),
            "own_rank": own_rank,
            "best_match_article_id": articles[int(order[0])]["article_id"],
            "best_match_title": articles[int(order[0])]["title"],
            "best_match_similarity": round(float(scores[int(order[0])]), 4),
            "best_other_article_id": articles[best_other_idx]["article_id"],
            "margin_vs_best_other": round(margin, 4),
            "top5": [
                {
                    "article_id": articles[int(idx)]["article_id"],
                    "similarity": round(float(scores[int(idx)]), 4),
                }
                for idx in order[:5]
            ],
        }
        row["_embedding_order"] = order.tolist()

    del embedding_model
    print(f"Loading reranker model: {args.reranker_model}")
    reranker = CrossEncoder(
        args.reranker_model,
        max_length=512,
        local_files_only=True,
        device="cpu",
    )
    rerank_candidates(
        reranker,
        rows,
        articles,
        article_index,
        args.shortlist_size,
        args.batch_size,
    )

    for row in rows:
        row.pop("_embedding_order", None)
        if row["decision"] == "PENDING":
            row["decision"] = "PASS_TO_SEMANTIC"

    payload = {
        "experiment": "reference-free deterministic-to-semantic funnel",
        "reference_summary_used": False,
        "test_summary_count": len(rows),
        "retrieval_article_count": len(articles),
        "test_selection": "first 10 articles in articles.jsonl, 5 summaries each",
        "models": {
            "embedding": args.embedding_model,
            "reranker": args.reranker_model,
        },
        "provisional_thresholds": {
            "copy": (
                "full containment OR longest>=50 and ratio>=0.50 OR "
                "longest>=30 and 12-char-shingle coverage>=0.85"
            ),
            "embedding_suspect": "own_rank>1 and margin_vs_best_other<=-0.10",
            "reranker_confirm": (
                "best article is not assigned article, assigned_score<=0.20, "
                "and margin_vs_best_other<=-0.50"
            ),
        },
        "counts": dict(Counter(row["decision"] for row in rows)),
        "results": rows,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(args.report, payload, articles_by_id)
    print(json.dumps(payload["counts"], ensure_ascii=False))
    print(f"JSON: {args.output}")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
