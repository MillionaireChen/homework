---
description: Score article-summary pairs through the reference-free quality funnel (physical hard gates → grounding gate → dual-agent scoring, every early exit reviewer-confirmed)
---

Use the evaluate-summary-quality skill to evaluate the article-summary pair(s) described below, and follow its cascade exactly.

Hard constraints come in two layers, and nothing terminates without the summary-reviewer agent confirming it:

1. Physical layer: run `scripts/hard_gate.py`. It proposes only what a string test can prove — empty output, more than three sentences, a continuous source copy, or truncation on a trailing comma/colon or unclosed delimiter. Give every proposal to summary-reviewer.
2. Required relevance stage: on survivors, run `scripts/embedding_gate.py` against a local Ollama server serving `qwen3-embedding:0.6b`. It compares a candidate with its own assigned article only. Every survivor must come out of this stage with a similarity value recorded in its trace, and the value is never terminal on its own — it nominates suspects for the next stage.
3. Semantic layer: run the summary-grounding-gate agent on every survivor. It answers only whether the candidate is grounded in its article, returning OFF_TOPIC, FACTUAL_REVERSAL, or FABRICATED_CONTENT when the defect is central. Give every proposal to summary-reviewer's grounding pass; a rejected proposal continues to scoring.
4. Scoring: generate one anchor per article, score survivors with summary-scorer, and review every draft with summary-reviewer. The reviewer may escalate FACTUAL_REVERSAL, FABRICATED_CONTENT, or OBVIOUS_TRUNCATION as a backstop.

A wrong peripheral number or secondary entity is a faithfulness penalty, never a terminal result. Validate with `scripts/validate_result.py` before delivering, rank within each article with `scripts/rank_results.py`, then hand the validated output to summary-reporter for the run report.

Input: $ARGUMENTS
