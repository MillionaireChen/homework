---
name: evaluate-summary-quality
description: Evaluate one or many article-summary pairs without requiring reference summaries. Use when Codex must score, label, rank, audit, or validate generated summaries; detect verbatim source copying, excessive sentence count, obvious truncation, or off-topic content; run structured Scorer, Reviewer, and Report Agents; or produce reproducible evaluation traces, JSON/JSONL results, charts, and a concise Markdown experiment report.
---

# Evaluate Summary Quality

Score summaries through a reference-free cascade. Keep routing state separate from final quality, record every visited stage, and require independent review before emitting a final result.

## Required references

Read these files before evaluating:

- `references/rubric.md` for hard gates, dimensions, and ranking.
- `references/agent-prompts.md` before launching or simulating the Scorer and Reviewer roles.
- `references/few-shot-examples.md` and inject exactly one matching example for the active case; do not load unrelated examples into a call.
- `references/output-schema.md` before finalizing any output.

Read `references/embedding-calibration.md` only when calibrating or defending the relevance gate.

## Workflow

1. Accept `article` and `summary`. Accept IDs when provided. Do not require or inspect `reference_summary`.
2. Run `scripts/hard_gate.py`. Treat its output as a draft route, not a final decision.
3. Give every proposed hard exit to the Reviewer role. Confirmed hard failures skip the Scorer Agent and receive their rubric-defined terminal ranking result. A rejected gate continues.
4. For survivors, optionally run `scripts/embedding_gate.py`. In multi-article batches, use own-article rank and margin to nominate off-topic cases. For a single pair, treat absolute similarity as a weak signal only.
5. Give every off-topic proposal to the Reviewer. A confirmed unrelated candidate receives score `0`, ranks last, and stops. Never hard-fail from embedding alone.
6. Only candidates that pass every hard gate qualify for soft scoring.
7. Generate one structured anchor per article before showing candidate summaries to the scoring pass. Cache and reuse it for every candidate of that article.
8. Run the Scorer role with the article, candidate, anchor, rubric, routing evidence, and prior trace. Require source-grounded claim checks and a draft soft score.
9. Run the independent Reviewer role on every draft. Pass only inputs, structured decisions, cited evidence, and calculations—not hidden reasoning.
10. On `REVISE`, let the Scorer revise once from explicit review findings, then review again. On unresolved disagreement, mark `LOW_CONFIDENCE` and preserve both positions.
11. Run `scripts/validate_result.py`. Do not deliver output until schema, score ranges, dimension sums, review status, and trace rules pass.
12. For five summaries per article, order terminal failure tiers first, then soft scores. Preserve evidence-backed ties.
13. Run `scripts/make_report_charts.py` on the validated result. When available, also pass hard-gate and embedding draft files so the funnel statistics distinguish initial catches from downstream recoveries.
14. Run the Report Agent with `report_stats.json`, chart paths, batch metadata, and concise audited findings. Require the four report sections, embed both charts, and keep the report below 800 lexical units.
15. Run `scripts/validate_report.py`. Deliver the machine-readable result and human-readable report together.

## Agent execution

Use three role-isolated agents when delegation is available:

- Scorer Agent: generate the article anchor in an article-only pass, then score candidates that passed every hard gate.
- Reviewer Agent: independently confirm every early exit and review every soft score and cited source span.
- Report Agent: summarize validated aggregate results and deterministic charts for a reader who will not inspect JSON/JSONL.

Prefer different models for the two roles when practical. Otherwise use separate prompts and fresh contexts. If delegation is unavailable, execute the roles sequentially with isolated prompts and preserve their separate outputs.

Every Agent call must include one relevant few-shot example from `references/few-shot-examples.md`. Select by stage and suspected condition. For a general soft-score call, use the closest dominant quality issue. Use `REPORT_SUMMARY` for the Report Agent. Never use evaluation targets from the current batch as few-shot examples.

## Efficiency rules

- Stop expensive work after a Reviewer-confirmed terminal failure.
- Do not embed confirmed copies, over-length outputs, or obvious truncations.
- Call a stronger relevance checker only on embedding suspects or boundary cases.
- Generate the anchor once per article, not once per summary.
- Reuse source chunks, embeddings, and anchors within a batch.
- Generate charts deterministically from final JSON/JSONL; do not ask the Report Agent to estimate counts or draw charts.
- Do not browse for new training or evaluation data while reporting. Treat autonomous corpus expansion as a separate, explicit future task with provenance and licensing controls.

## Scripts

- `scripts/hard_gate.py`: deterministic draft gates and trace creation for JSON or JSONL input.
- `scripts/embedding_gate.py`: optional Ollama embedding evidence for single pairs or multi-article batches; pass `--article-corpus` when testing a summary subset against a larger article bank.
- `scripts/validate_result.py`: final schema, arithmetic, review, and trace validation.
- `scripts/rank_results.py`: rank validated results within each article while keeping off-topic last.
- `scripts/make_report_charts.py`: derive audited batch statistics and two fixed PNG charts from final JSON/JSONL.
- `scripts/validate_report.py`: enforce the four-section Markdown structure, local chart presence, and 800-unit length limit.

Use `python3 <script> --help` for CLI options.
