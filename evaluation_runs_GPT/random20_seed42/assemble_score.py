#!/usr/bin/env python3
"""Assemble the reviewed random-20 pipeline artifacts into canonical JSONL."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read_json(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def read_jsonl(name: str):
    return [
        json.loads(line)
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def by_summary(rows):
    return {row["summary_id"]: row for row in rows}


inputs = read_jsonl("inputs.jsonl")
hard = by_summary(read_jsonl("hard_gate_drafts.jsonl"))
embedding = by_summary(read_jsonl("embedding_drafts.jsonl"))
drafts = by_summary(read_json("scorer_drafts_a.json") + read_json("scorer_drafts_b.json"))
reviews = by_summary(read_json("review_results.json"))
final_reviews = by_summary(read_json("final_revision_review.json"))

revised_a = read_json("revised_a.json")
revised_b = read_json("revised_b.json")
revisions = by_summary([revised_a] + revised_b)


def approved_review(summary_id: str, rounds: int, findings):
    return {
        "decision": "APPROVE",
        "rounds": rounds,
        "confidence": "HIGH",
        "findings": findings,
    }


def terminal_from_hard(row):
    terminal = row["draft_terminal_result"]
    evidence = row["evaluation_trace"][0]["evidence"]
    return {
        "article_id": row["article_id"],
        "summary_id": row["summary_id"],
        "eligible_for_soft_scoring": False,
        "score": 0,
        "terminal_result": terminal,
        "terminal_rank": row["terminal_rank"],
        "quality_label": "HARD_FAIL_COPY",
        "hard_fail": True,
        "hard_fail_reason": terminal,
        "dimensions": None,
        "anchor": None,
        "claim_checks": [],
        "issues": ["The normalized candidate is fully contained in the article and is a verbatim source copy."],
        "review": approved_review(
            row["summary_id"],
            1,
            ["Approved the terminal result because the normalized candidate is fully contained in the article and every copy metric equals 1.0."],
        ),
        "evaluation_trace": row["evaluation_trace"]
        + [
            {
                "stage": "terminal_review",
                "result": "APPROVE",
                "evidence": {"confidence": "HIGH", "terminal_result": terminal},
            },
            {
                "stage": "early_stop",
                "result": terminal,
                "evidence": {
                    "copy_metrics": evidence,
                    "skipped_stages": ["sentence_count", "truncation_check", "embedding_relevance", "anchor_generation", "soft_scoring"],
                },
            },
        ],
    }


def terminal_off_topic(row):
    evidence = row["embedding_evidence"]
    return {
        "article_id": row["article_id"],
        "summary_id": row["summary_id"],
        "eligible_for_soft_scoring": False,
        "score": 0,
        "terminal_result": "OFF_TOPIC",
        "terminal_rank": 0,
        "quality_label": "HARD_FAIL_OFF_TOPIC",
        "hard_fail": True,
        "hard_fail_reason": "OFF_TOPIC",
        "dimensions": None,
        "anchor": None,
        "claim_checks": [],
        "issues": ["The article concerns a Thai cave rescue, while the candidate concerns Scotch whisky sales; the subjects, events, and topics do not match."],
        "review": approved_review(
            row["summary_id"],
            1,
            ["Approved OFF_TOPIC because the assigned article ranked 14th at similarity 0.3193 and independent semantic review confirmed a completely different topic."],
        ),
        "evaluation_trace": row["evaluation_trace"]
        + [
            {
                "stage": "terminal_review",
                "result": "APPROVE",
                "evidence": {"confidence": "HIGH", "semantic_finding": "The subject, event, and topic are completely mismatched."},
            },
            {
                "stage": "early_stop",
                "result": "OFF_TOPIC",
                "evidence": {"embedding": evidence, "skipped_stages": ["anchor_generation", "soft_scoring"]},
            },
        ],
    }


def terminal_truncation(summary_id: str):
    row = dict(revisions.get(summary_id, drafts[summary_id]))
    first_review = reviews[summary_id]
    final_review = final_reviews.get(summary_id)
    row["eligible_for_soft_scoring"] = False
    row["score"] = 0
    row["terminal_result"] = "OBVIOUS_TRUNCATION"
    row["terminal_rank"] = 2
    row["quality_label"] = "HARD_FAIL_TRUNCATION"
    row["hard_fail"] = True
    row["hard_fail_reason"] = "OBVIOUS_TRUNCATION"
    row["dimensions"] = None
    row["anchor"] = None
    row["claim_checks"] = []
    rounds = 2 if final_review else 1
    findings = list(first_review.get("findings", []))
    if final_review:
        findings += final_review.get("findings", [])
    row["review"] = approved_review(summary_id, rounds, findings)
    trace = list(row.get("evaluation_trace", []))
    if not any(event.get("stage") == "early_stop" for event in trace):
        trace += [
            {
                "stage": "terminal_review",
                "result": "APPROVE",
                "evidence": {"confidence": "HIGH", "terminal_result": "OBVIOUS_TRUNCATION"},
            },
            {
                "stage": "early_stop",
                "result": "OBVIOUS_TRUNCATION",
                "evidence": {"skipped_stages": ["anchor_generation", "soft_scoring"]},
            },
        ]
    else:
        trace += [
            {
                "stage": "final_revision_review",
                "result": "APPROVE",
                "evidence": {"confidence": "HIGH", "terminal_result": "OBVIOUS_TRUNCATION"},
            }
        ]
    row["evaluation_trace"] = trace
    row.pop("status", None)
    return row


def soft_result(summary_id: str):
    row = dict(revisions.get(summary_id, drafts[summary_id]))
    review = reviews[summary_id]
    final_review = final_reviews.get(summary_id)
    row["eligible_for_soft_scoring"] = True
    row["terminal_result"] = None
    row["terminal_rank"] = None
    row["hard_fail"] = False
    row["hard_fail_reason"] = None
    rounds = 2 if final_review else 1
    findings = list(review.get("findings", []))
    if final_review:
        findings += final_review.get("findings", [])
    row["review"] = approved_review(summary_id, rounds, findings)
    base_trace = list(embedding[summary_id]["evaluation_trace"])
    base_trace.append(
        {
            "stage": "anchor_and_draft_scoring",
            "result": "DRAFT" if not final_review else "REVISED",
            "evidence": {"few_shot": row.get("few_shot_used")},
        }
    )
    if final_review:
        base_trace += [
            {
                "stage": "draft_review",
                "result": "REVISE",
                "evidence": {"confidence": review["confidence"], "findings": review.get("findings", [])},
            },
            {
                "stage": "scorer_revision",
                "result": "APPLIED",
                "evidence": {"dimensions": row["dimensions"], "score": row["score"], "quality_label": row["quality_label"]},
            },
            {
                "stage": "final_revision_review",
                "result": "APPROVE",
                "evidence": {"confidence": final_review["confidence"], "findings": final_review.get("findings", [])},
            },
        ]
    else:
        base_trace.append(
            {
                "stage": "draft_review",
                "result": "APPROVE",
                "evidence": {"confidence": review["confidence"], "findings": review.get("findings", [])},
            }
        )
    row["evaluation_trace"] = base_trace
    row.pop("status", None)
    return row


results = []
for source in inputs:
    summary_id = source["summary_id"]
    hard_row = hard[summary_id]
    embedding_row = embedding.get(summary_id)
    if hard_row.get("draft_terminal_result"):
        result = terminal_from_hard(hard_row)
    elif embedding_row and embedding_row.get("embedding_evidence", {}).get("off_topic_suspect"):
        result = terminal_off_topic(embedding_row)
    elif summary_id in {"52000333_a8b27666", "36881141_86804cfb"}:
        result = terminal_truncation(summary_id)
    else:
        result = soft_result(summary_id)
    result["sample_order"] = len(results) + 1
    results.append(result)

assert len(results) == 20
assert {row["summary_id"] for row in results} == {row["summary_id"] for row in inputs}

(ROOT / "score_unranked.jsonl").write_text(
    "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results),
    encoding="utf-8",
)
