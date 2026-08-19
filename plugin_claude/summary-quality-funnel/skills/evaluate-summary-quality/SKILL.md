---
name: evaluate-summary-quality
description: Evaluate one or many article-summary pairs without requiring reference summaries. Use when Claude must score, label, rank, audit, or validate generated summaries; detect verbatim source copying, excessive sentence count, obvious truncation, or off-topic content; run a structured Scorer agent and independent Reviewer agent; or produce reproducible evaluation traces and JSON/JSONL results.
---

# Evaluate Summary Quality

Score summaries through a reference-free cascade. Keep routing state separate from final quality, record every visited stage, and require independent review before emitting a final result.

## Required references

Read these files before evaluating (all paths relative to this skill directory; when invoked as an installed plugin, resolve them under `${CLAUDE_PLUGIN_ROOT}/skills/evaluate-summary-quality/`):

- `references/rubric.md` for hard gates, dimensions, and ranking.
- `references/agent-prompts.md` before launching the Scorer and Reviewer subagents.
- `references/few-shot-examples.md` and inject exactly one matching example for the active case; do not load unrelated examples into a call.
- `references/output-schema.md` before finalizing any output.

Read `references/embedding-calibration.md` only when calibrating or defending the relevance gate.

## Workflow

1. Accept `article` and `summary`. Accept IDs when provided. Do not require or inspect `reference_summary`.
2. Run `scripts/hard_gate.py`. Treat its output as a draft route, not a final decision.
3. Give every proposed hard exit to the Reviewer subagent. Confirmed hard failures skip the Scorer and receive their rubric-defined terminal ranking result. A rejected gate continues.
4. For survivors, optionally run `scripts/embedding_gate.py` (requires a local Ollama server with `qwen3-embedding:0.6b`). In multi-article batches, use own-article rank and margin to nominate off-topic cases. For a single pair, treat absolute similarity as a weak signal only.
5. Give every off-topic proposal to the Reviewer. A confirmed unrelated candidate receives score `0`, ranks last, and stops. Never hard-fail from embedding alone.
6. Only candidates that pass every hard gate qualify for soft scoring.
7. Generate one structured anchor per article before showing candidate summaries to the scoring pass. Cache and reuse it for every candidate of that article.
8. Run the Scorer subagent with the article, candidate, anchor, rubric, routing evidence, and prior trace. Require source-grounded claim checks and a draft soft score.
9. Run the independent Reviewer subagent on every draft. Pass only inputs, structured decisions, cited evidence, and calculations — not hidden reasoning.
10. On `REVISE`, let the Scorer revise once from explicit review findings, then review again. On unresolved disagreement, mark `LOW_CONFIDENCE` and preserve both positions.
11. Run `scripts/validate_result.py`. Do not deliver output until schema, score ranges, dimension sums, review status, and trace rules pass.
12. For five summaries per article, order terminal failure tiers first, then soft scores. Preserve evidence-backed ties. Use `scripts/rank_results.py`.

## Agent execution

Use the two plugin subagents via the Agent tool, and run them as separate calls so their contexts stay isolated:

- **`summary-scorer`**: generate the article anchor in an article-only pass, then score candidates that passed every hard gate. When evaluating a batch, launch one scorer per article and let it handle all of that article's eligible candidates (the anchor is generated once and reused).
- **`summary-reviewer`**: independently confirm every early exit (hard-gate drafts and embedding off-topic nominations) and review every soft score and cited source span. Never reuse a scorer's context for review.

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
- `scripts/embedding_gate.py`: optional Ollama embedding evidence for single pairs or multi-article batches; pass `--article-corpus` when testing a summary subset against a larger article bank.
- `scripts/validate_result.py`: final schema, arithmetic, review, and trace validation.
- `scripts/rank_results.py`: rank validated results within each article while keeping off-topic last.

Use `python3 <script> --help` for CLI options.
