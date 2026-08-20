# Output schema

Return one object per article-summary pair.

```json
{
  "article_id": "optional",
  "summary_id": "optional",
  "eligible_for_soft_scoring": true,
  "score": 72,
  "terminal_rank": null,
  "quality_label": "MIXED",
  "hard_fail": false,
  "hard_fail_reason": null,
  "dimensions": {
    "faithfulness": 42,
    "coverage": 18,
    "coherence": 9,
    "conciseness": 3
  },
  "anchor": {
    "main_event": "...",
    "key_facts": ["..."],
    "anchor_summary": "..."
  },
  "claim_checks": [],
  "issues": [],
  "review": {
    "decision": "APPROVE",
    "rounds": 1,
    "confidence": "HIGH",
    "findings": []
  },
  "evaluation_trace": []
}
```

## Invariants

- `score` is numeric within `0–100`.
- Eligible dimension values respect maxima `50/30/15/5` and sum to `score`.
- Reviewer-confirmed terminal failures have `eligible_for_soft_scoring: false`, `score: 0`, `dimensions: null`, a terminal label/rank, and an `early_stop` trace event.
- `OFF_TOPIC` always has `terminal_rank: 0` and ranks last.
- `FACTUAL_REVERSAL` always has `terminal_rank: 0` and `quality_label: HARD_FAIL_REVERSAL`; `FABRICATED_CONTENT` always has `terminal_rank: 0` and `quality_label: HARD_FAIL_FABRICATION`.
- Both carry a `grounding_gate` trace event, a `grounding_review` event with the Reviewer's decision, and source spans in `source_evidence`. They arrive from a Reviewer-confirmed Grounding Gate proposal, or from a Reviewer-confirmed soft-score escalation when the gate missed the defect. A deterministic gate may never produce them.
- Final non-escalated results have `review.decision: APPROVE`.
- Every visited stage has a trace event. Skipped expensive stages appear in the hard-fail `early_stop` event.
- Evidence contains short source spans, not model chain-of-thought.
- Never include or require `reference_summary`.

## Batch report artifacts

For batch experiments, deliver these alongside the validated score records:

- `report_assets_stats.json`: deterministic aggregate statistics from the ranked score file.
- `report_assets/funnel.png`: stage-by-stage survival chart.
- `report_assets/scores_by_article.png`: per-article ranking chart.
- `report_assets/categories.png`: outcome-category chart.
- `report_assets/reference_validation.png` and `reference_validation.json`, when the Report Agent runs the offline reference cross-check.
- `report.md`: Report Agent Markdown, under 800 words, with the fixed sections and every chart embedded.

The report is descriptive and must not replace the per-record evidence or Reviewer decision.
