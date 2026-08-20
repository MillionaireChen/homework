---
name: evaluate-summary-quality
description: Evaluate one or many article-summary pairs without requiring reference summaries. Use when Claude must score, label, rank, audit, or validate generated summaries; detect verbatim source copying, excessive sentence count, obvious truncation, off-topic content, factual reversal, or fabricated content; run a Grounding Gate agent, a Scorer agent, and an independent Reviewer agent; or produce reproducible evaluation traces and JSON/JSONL results.
---

# Evaluate Summary Quality

Score summaries through a reference-free cascade. Keep routing state separate from final quality, record every visited stage, and require independent review before emitting a final result.

## Required references

Read these files before evaluating (all paths relative to this skill directory; when invoked as an installed plugin, resolve them under `${CLAUDE_PLUGIN_ROOT}/skills/evaluate-summary-quality/`):

- `references/rubric.md` for hard gates, dimensions, and ranking.
- `references/agent-prompts.md` before launching the Grounding Gate, Scorer, and Reviewer subagents.
- `references/few-shot-examples.md` and inject exactly one matching example for the active case; do not load unrelated examples into a call.
- `references/output-schema.md` before finalizing any output.

Read `references/embedding-calibration.md` only when calibrating or defending the relevance gate.

## Workflow

1. Accept `article` and `summary`. Accept IDs when provided. Do not require or inspect `reference_summary`.
2. Run `scripts/hard_gate.py`. Treat its output as a draft route, not a final decision.
3. Give every proposed hard exit to the Reviewer subagent. Confirmed hard failures skip the Scorer and receive their rubric-defined terminal ranking result. A rejected gate continues.
4. For survivors, optionally run `scripts/embedding_gate.py` (requires a local Ollama server with `qwen3-embedding:0.6b`). A candidate is compared only with its own assigned article, never with another article, whether or not the batch contains one. Similarity below the threshold is a cheap hint for the next step and is never terminal on its own.
5. Run the **`summary-grounding-gate`** subagent on every survivor. This is the semantic hard constraint and the last line of defence before scoring: it decides only whether the candidate is grounded in its article, returning `NOT_GROUNDED` with one central category, `OFF_TOPIC`, `FACTUAL_REVERSAL`, or `FABRICATED_CONTENT`, plus one article span and one candidate span. It never scores.
6. Give every gate proposal to the Reviewer's grounding pass. A confirmed proposal receives score `0`, `terminal_rank` `0`, and stops before anchor generation. A rejected proposal continues to scoring with both positions kept in the trace. Never terminate on the gate's word alone.
7. Only candidates that clear both hard-constraint layers, the physical string gates and the semantic grounding gate, qualify for soft scoring.
8. Generate one structured anchor per article before showing candidate summaries to the scoring pass. Cache and reuse it for every candidate of that article.
9. Run the Scorer subagent with the article, candidate, anchor, rubric, routing evidence, and prior trace. Require source-grounded claim checks and a draft soft score.
10. Run the independent Reviewer subagent on every draft. Pass only inputs, structured decisions, cited evidence, and calculations — not hidden reasoning.
11. Keep the semantic terminals reachable here as a backstop for whatever the grounding gate missed. When a claim check shows a central reversal or a central fabrication, the Scorer proposes and the Reviewer confirms `FACTUAL_REVERSAL` or `FABRICATED_CONTENT` with score `0` and `terminal_rank` `0`. A wrong peripheral number or secondary entity stays a soft faithfulness penalty. The Reviewer may also escalate `OBVIOUS_TRUNCATION` here when the candidate physically stops mid-thought, since the gate proposes truncation only on provable string evidence.
12. On `REVISE`, let the Scorer revise once from explicit review findings, then review again. On unresolved disagreement, mark `LOW_CONFIDENCE` and preserve both positions.
13. Run `scripts/validate_result.py`. Do not deliver output until schema, score ranges, dimension sums, review status, and trace rules pass.
14. For five summaries per article, order terminal failure tiers first, then soft scores. Preserve evidence-backed ties. Use `scripts/rank_results.py`.
15. After validation and ranking, produce the run report: run `scripts/make_report_charts.py` on the ranked JSONL, then launch the **`summary-reporter`** subagent with the ranked JSONL path, the stats JSON, and the chart directory. Supply the article and summary corpus as well when an offline reference cross-check is wanted; the reporter is the only role permitted to read `reference_summary`, and only after every score is final. The report is English Markdown, under 800 words, with the fixed sections and every chart embedded. The reporter consumes validated output only and never invents numbers.

## Agent execution

Use the four plugin subagents via the Agent tool, and run them as separate calls so their contexts stay isolated:

- **`summary-grounding-gate`**: decide only whether a candidate is grounded in its article. It sees the article and the candidate, never the anchor, never the soft rubric, never another article, and it never produces a score. Keeping it out of the Scorer's context is deliberate: one agent that both screens and scores will trade a central defect for a low score instead of stopping it.
- **`summary-scorer`**: generate the article anchor in an article-only pass, then score candidates that cleared both hard-constraint layers. When evaluating a batch, launch one scorer per article and let it handle all of that article's eligible candidates (the anchor is generated once and reused).
- **`summary-reviewer`**: independently confirm every early exit (hard-gate drafts and grounding-gate proposals) and review every soft score and cited source span. Never reuse a scorer's context for review.
- **`summary-reporter`**: write the run report from validated output only.

Launch independent scorer calls for different articles in parallel. If subagent delegation is unavailable, execute the roles sequentially with isolated prompts and preserve their separate outputs.

Every subagent call must include one relevant few-shot example from `references/few-shot-examples.md`. Select by stage and suspected condition. For a general soft-score call, use the closest dominant quality issue. Never use evaluation targets from the current batch as few-shot examples.

## Efficiency rules

- Stop expensive work after a Reviewer-confirmed terminal failure.
- Do not embed confirmed copies, over-length outputs, or obvious truncations.
- Call a stronger relevance checker only on embedding suspects or boundary cases.
- Generate the anchor once per article, not once per summary.
- Reuse source chunks, embeddings, and anchors within a batch.

## Scripts

- `scripts/hard_gate.py`: deterministic draft gates and trace creation for JSON or JSONL input.
- `scripts/embedding_gate.py`: optional Ollama similarity between a candidate and its own assigned article. Cross-article comparison is prohibited, so the script accepts no article bank and emits no rank, best-match, or margin evidence.
- `scripts/validate_result.py`: final schema, arithmetic, review, and trace validation.
- `scripts/rank_results.py`: rank validated results within each article while keeping off-topic last.
- `scripts/make_report_charts.py`: deterministic funnel/score/category charts + stats JSON from a ranked JSONL, consumed by the `summary-reporter` agent.
- `scripts/reference_validation.py`: offline reference cross-check for a finished run. Report stage only; it labels candidates from the corpus alone, joins the score file afterwards, and emits `reference_validation.json` plus a chart.

Use `python3 <script> --help` for CLI options.
