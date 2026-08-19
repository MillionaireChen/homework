#!/usr/bin/env python3
"""Compare candidate-to-article and candidate-to-anchor embeddings on random20."""

from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
MODEL = "qwen3-embedding:0.6b"
ENDPOINT = "http://127.0.0.1:11434/api/embed"

MANUAL_ANCHORS = {
    "36881141": "北京のサファリパークで、車を降りた女性がトラに襲われ、助けようと降車した別の女性も別のトラに襲われて死亡した。最初の女性は負傷して治療を受け、同行男性は無事だった。",
    "37868736": "英高等法院は、政府が議会承認なしにEU離脱手続きの第50条を発動する権限はないと判断した。政府は上訴する方針だが、メイ首相は翌年3月末までに離脱手続きを始める予定を維持している。",
    "40504740": "ベトナムは、中国と領有権を争う南シナ海の海域で石油掘削を開始した。現場は両国が別々の名称で権利を主張する海域で、中国の反発が懸念されている。",
    "44708203": "タイの洞窟で9日間行方不明だった少年12人と監督が発見され、公開動画で元気な姿を見せた。食料と治療を受けているが、潜水習得か水位低下を待つ必要があり、救出に数カ月かかる可能性がある。",
}


def load_json(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def load_jsonl(name):
    return [
        json.loads(line)
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def embed(texts, batch_size=25):
    vectors = []
    for start in range(0, len(texts), batch_size):
        payload = json.dumps(
            {"model": MODEL, "input": texts[start : start + batch_size]}
        ).encode("utf-8")
        request = urllib.request.Request(
            ENDPOINT, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=600) as response:
            vectors.extend(json.loads(response.read().decode("utf-8"))["embeddings"])
    return vectors


def cosine(left, right):
    dot = sum(a * b for a, b in zip(left, right))
    nl = math.sqrt(sum(a * a for a in left))
    nr = math.sqrt(sum(b * b for b in right))
    return dot / (nl * nr) if nl and nr else 0.0


def pearson(xs, ys):
    if len(xs) < 2:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    numerator = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return numerator / (dx * dy) if dx and dy else None


def ranks(values):
    ordered = sorted(range(len(values)), key=lambda i: values[i])
    output = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        average_rank = (start + 1 + end) / 2
        for position in range(start, end):
            output[ordered[position]] = average_rank
        start = end
    return output


def spearman(xs, ys):
    return pearson(ranks(xs), ranks(ys))


scores = load_json("score.json")
score_by_id = {row["summary_id"]: row for row in scores}
inputs = load_jsonl("inputs.jsonl")
input_by_id = {row["summary_id"]: row for row in inputs}
embedding_rows = load_jsonl("embedding_drafts.jsonl")

anchor_by_article = {}
for row in scores:
    if row.get("anchor"):
        anchor_by_article.setdefault(row["article_id"], row["anchor"]["anchor_summary"])
anchor_by_article.update(MANUAL_ANCHORS)

sampled_article_ids = sorted({row["article_id"] for row in inputs})
missing = sorted(set(sampled_article_ids) - set(anchor_by_article))
if missing:
    raise RuntimeError(f"missing anchors: {missing}")

candidate_texts = [input_by_id[row["summary_id"]]["summary"] for row in embedding_rows]
anchor_vectors = embed([anchor_by_article[article_id] for article_id in sampled_article_ids])
candidate_vectors = embed(candidate_texts)

details = []
for embedding_row, candidate_vector in zip(embedding_rows, candidate_vectors):
    summary_id = embedding_row["summary_id"]
    result = score_by_id[summary_id]
    similarities = [cosine(candidate_vector, vector) for vector in anchor_vectors]
    order = sorted(range(len(similarities)), key=lambda index: similarities[index], reverse=True)
    assigned_index = sampled_article_ids.index(embedding_row["article_id"])
    assigned_rank = order.index(assigned_index) + 1
    best_other = next(index for index in order if index != assigned_index)
    details.append(
        {
            "article_id": embedding_row["article_id"],
            "summary_id": summary_id,
            "eligible_for_soft_scoring": result["eligible_for_soft_scoring"],
            "score": result["score"],
            "coverage": result["dimensions"]["coverage"] if result["dimensions"] else None,
            "faithfulness": result["dimensions"]["faithfulness"] if result["dimensions"] else None,
            "terminal_result": result.get("terminal_result"),
            "article_similarity": embedding_row["embedding_evidence"]["assigned_similarity"],
            "article_rank_in_50": embedding_row["embedding_evidence"]["assigned_rank"],
            "anchor_similarity": round(similarities[assigned_index], 4),
            "anchor_rank_in_sampled_14": assigned_rank,
            "anchor_best_match_article_id": sampled_article_ids[order[0]],
            "anchor_margin_vs_best_other": round(
                similarities[assigned_index] - similarities[best_other], 4
            ),
        }
    )

eligible = [row for row in details if row["eligible_for_soft_scoring"]]


def correlation_block(target):
    target_values = [row[target] for row in eligible]
    article_values = [row["article_similarity"] for row in eligible]
    anchor_values = [row["anchor_similarity"] for row in eligible]
    return {
        "article_embedding": {
            "pearson": round(pearson(article_values, target_values), 4),
            "spearman": round(spearman(article_values, target_values), 4),
        },
        "anchor_embedding": {
            "pearson": round(pearson(anchor_values, target_values), 4),
            "spearman": round(spearman(anchor_values, target_values), 4),
        },
    }


def distribution(rows, field):
    values = [row[field] for row in rows]
    return {
        "n": len(values),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "mean": round(sum(values) / len(values), 4),
    }


def coverage_loocv(fields):
    target = np.array([row["coverage"] for row in eligible], dtype=float)
    design = np.array(
        [[1.0] + [row[field] for field in fields] for row in eligible],
        dtype=float,
    )
    predictions = []
    for held_out in range(len(target)):
        keep = np.arange(len(target)) != held_out
        coefficients = np.linalg.lstsq(
            design[keep], target[keep], rcond=None
        )[0]
        predictions.append(float(design[held_out] @ coefficients))
    predicted = np.array(predictions)
    errors = predicted - target
    return {
        "features": fields,
        "mae": round(float(np.abs(errors).mean()), 4),
        "rmse": round(float(np.sqrt((errors ** 2).mean())), 4),
    }


report = {
    "experiment": "candidate-to-article vs candidate-to-anchor embedding ablation",
    "model": MODEL,
    "sample_seed": 42,
    "notes": [
        "No reference summary was used.",
        "Only the 15 hard-gate survivors were embedded; five verbatim copies stopped earlier.",
        "Article retrieval ranks came from the existing 50-article corpus run; anchor ranks use the 14 unique articles in this sample.",
        "Correlations use only the 12 Reviewer-approved soft-scored summaries.",
    ],
    "correlations": {
        "coverage": correlation_block("coverage"),
        "total_score": correlation_block("score"),
        "faithfulness": correlation_block("faithfulness"),
    },
    "coverage_prediction_loocv": {
        "article_only": coverage_loocv(["article_similarity"]),
        "anchor_only": coverage_loocv(["anchor_similarity"]),
        "article_plus_anchor": coverage_loocv(
            ["article_similarity", "anchor_similarity"]
        ),
    },
    "similarity_distributions": {
        "soft_scored_article": distribution(eligible, "article_similarity"),
        "soft_scored_anchor": distribution(eligible, "anchor_similarity"),
        "off_topic_article": distribution(
            [row for row in details if row["terminal_result"] == "OFF_TOPIC"],
            "article_similarity",
        ),
        "off_topic_anchor": distribution(
            [row for row in details if row["terminal_result"] == "OFF_TOPIC"],
            "anchor_similarity",
        ),
    },
    "details": details,
    "article_anchors": [
        {"article_id": article_id, "anchor_summary": anchor_by_article[article_id]}
        for article_id in sampled_article_ids
    ],
}

(ROOT / "anchor_embedding_ablation_GPT.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

columns = [
    "summary_id",
    "score",
    "coverage",
    "faithfulness",
    "terminal_result",
    "article_similarity",
    "anchor_similarity",
    "article_rank_in_50",
    "anchor_rank_in_sampled_14",
]
lines = ["\t".join(columns)]
for row in details:
    lines.append("\t".join(str(row.get(column, "")) for column in columns))
(ROOT / "anchor_embedding_ablation_GPT.tsv").write_text(
    "\n".join(lines) + "\n", encoding="utf-8"
)
