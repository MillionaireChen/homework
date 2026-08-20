#!/usr/bin/env python3
"""Assemble terminal routes and independently reviewed soft scores into JSONL."""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path


TERMINAL_META = {
    "EMPTY_OUTPUT": (0, "HARD_FAIL_EMPTY"),
    "OFF_TOPIC": (0, "HARD_FAIL_OFF_TOPIC"),
    # Semantic terminals: raised by the Grounding Gate, or by soft-score escalation as
    # a backstop. Never by a deterministic gate, since no string or embedding test
    # detects a reversal or a fabrication.
    "FACTUAL_REVERSAL": (0, "HARD_FAIL_REVERSAL"),
    "FABRICATED_CONTENT": (0, "HARD_FAIL_FABRICATION"),
    "VERBATIM_SOURCE_COPY": (1, "HARD_FAIL_COPY"),
    "OBVIOUS_TRUNCATION": (2, "HARD_FAIL_TRUNCATION"),
    "OVER_SENTENCE_LIMIT": (3, "HARD_FAIL_OVER_LENGTH"),
}


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_glob(pattern: str):
    return [row for name in sorted(glob.glob(pattern)) for row in read_jsonl(Path(name))]


def unique_index(rows, label):
    index = {}
    for row in rows:
        key = str(row["summary_id"])
        if key in index:
            raise SystemExit(f"duplicate {label} summary_id: {key}")
        index[key] = row
    return index


def review_event(row):
    return row.get("review_trace_event") or row.get("terminal_review_trace_event")


def finalized_soft(draft, review, rounds, trace):
    result = dict(draft)
    result.pop("draft_status", None)
    result.pop("revision_notes", None)
    result.update({
        "eligible_for_soft_scoring": True,
        "terminal_result": None,
        "terminal_rank": None,
        "hard_fail": False,
        "hard_fail_reason": None,
        "review": {
            "decision": review["decision"],
            "rounds": rounds,
            "confidence": review["confidence"],
            "findings": review.get("findings", []),
        },
        "evaluation_trace": trace,
    })
    return result


def recovered_terminal(draft, soft_review, terminal_review):
    terminal = terminal_review["proposed_terminal_result"]
    rank, label = TERMINAL_META[terminal]
    terminal_event = review_event(terminal_review)
    trace = list(draft.get("evaluation_trace", []))
    trace.append(soft_review["review_trace_event"])
    trace.append(terminal_event)
    trace.append({
        "stage": "early_stop",
        "result": terminal,
        "evidence": {"recovered_during_soft_review": True, "skipped_stages": []},
    })
    return {
        "article_id": draft.get("article_id"),
        "summary_id": draft.get("summary_id"),
        "eligible_for_soft_scoring": False,
        "score": 0,
        "terminal_result": terminal,
        "terminal_rank": rank,
        "quality_label": label,
        "hard_fail": True,
        "hard_fail_reason": terminal,
        "dimensions": None,
        "anchor": None,
        "claim_checks": [],
        "issues": terminal_review.get("findings", []),
        "source_evidence": [],
        "few_shot_used": terminal_review.get("few_shot_used"),
        "review": {
            "decision": "APPROVE",
            "rounds": 2,
            "confidence": terminal_review.get("confidence"),
            "findings": terminal_review.get("findings", []),
        },
        "evaluation_trace": trace,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_dir = args.run_dir

    inputs = read_jsonl(run_dir / "inputs.jsonl")
    base_terminal = read_jsonl(run_dir / "hard_terminal_results.jsonl") + read_jsonl(run_dir / "off_topic_terminal_results.jsonl")
    drafts = read_glob(str(run_dir / "scorer_outputs" / "scorer_drafts_batch_*.jsonl"))
    reviews = read_glob(str(run_dir / "reviewer_outputs" / "reviews_batch_*.jsonl"))
    revisions = read_glob(str(run_dir / "scorer_outputs" / "revised_drafts_batch_*.jsonl"))
    final_reviews = read_glob(str(run_dir / "reviewer_outputs" / "final_reviews_batch_*.jsonl"))
    late_terminal = read_glob(str(run_dir / "reviewer_outputs" / "late_terminal_reviews_batch_*.jsonl"))

    terminal_by_id = unique_index(base_terminal, "base terminal")
    draft_by_id = unique_index(drafts, "draft")
    review_by_id = unique_index(reviews, "review")
    revision_by_id = unique_index(revisions, "revision")
    final_review_by_id = unique_index(final_reviews, "final review")
    late_by_id = unique_index(late_terminal, "late terminal review")

    soft_results = {}
    for summary_id, draft in draft_by_id.items():
        review = review_by_id.get(summary_id)
        if review is None:
            raise SystemExit(f"missing independent review: {summary_id}")
        decision = review["decision"]
        if decision == "APPROVE":
            trace = list(draft.get("evaluation_trace", [])) + [review["review_trace_event"]]
            soft_results[summary_id] = finalized_soft(draft, review, 1, trace)
        elif decision == "REVISE":
            revision = revision_by_id.get(summary_id)
            final_review = final_review_by_id.get(summary_id)
            if revision is None or final_review is None:
                raise SystemExit(f"missing revision or final review: {summary_id}")
            revision_events = [event for event in revision.get("evaluation_trace", []) if event.get("stage") == "score_revision"]
            if len(revision_events) != 1:
                raise SystemExit(f"invalid score_revision trace: {summary_id}")
            trace = list(draft.get("evaluation_trace", [])) + [review["review_trace_event"], revision_events[0], final_review["review_trace_event"]]
            soft_results[summary_id] = finalized_soft(revision, final_review, 2, trace)
        elif decision == "ESCALATE":
            late = late_by_id.get(summary_id)
            if late is None or late.get("decision") != "APPROVE":
                raise SystemExit(f"unresolved late terminal review: {summary_id}")
            soft_results[summary_id] = recovered_terminal(draft, review, late)
        else:
            raise SystemExit(f"invalid review decision for {summary_id}: {decision}")

    combined = {**terminal_by_id, **soft_results}
    expected_ids = [str(row["summary_id"]) for row in inputs]
    if set(combined) != set(expected_ids):
        missing = sorted(set(expected_ids) - set(combined))
        extra = sorted(set(combined) - set(expected_ids))
        raise SystemExit(f"final IDs differ; missing={missing}, extra={extra}")
    output_rows = [combined[summary_id] for summary_id in expected_ids]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in output_rows) + "\n", encoding="utf-8")
    print(f"assembled {len(output_rows)} results: terminal={sum(not row['eligible_for_soft_scoring'] for row in output_rows)} soft={sum(row['eligible_for_soft_scoring'] for row in output_rows)}")


if __name__ == "__main__":
    main()
