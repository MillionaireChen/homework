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
4. For survivors, run `scripts/embedding_gate.py`. **This stage is required**, and it requires a local Ollama server serving `qwen3-embedding:0.6b`. Every survivor must carry a similarity value in its trace; a run without embedding evidence is incomplete, not cheaper. A candidate is compared only with its own assigned article; never with another article, whether or not the batch contains one. Similarity below the threshold nominates the candidate for close reading at the next stage and is never terminal on its own. Required evidence, never a decision.
5. Run the Grounding Gate Agent on every survivor. This is the semantic hard constraint and the last line of defence before scoring: it judges only whether the candidate is grounded in the article, and returns `NOT_GROUNDED` with one central category, `OFF_TOPIC`, `FACTUAL_REVERSAL`, or `FABRICATED_CONTENT`. It never scores. Validate its output with `scripts/validate_grounding_outputs.py`.
6. Give every gate proposal to the Reviewer's grounding pass, then apply the decisions with `scripts/apply_grounding_reviews.py`. A confirmed proposal receives score `0`, `terminal_rank` `0`, and stops before anchor generation. A rejected proposal continues to scoring with both positions kept in the trace. Never terminate on the gate's word alone.
7. Only candidates that clear both hard-constraint layers qualify for soft scoring.
8. Generate one structured anchor per article before showing candidate summaries to the scoring pass. Cache and reuse it for every candidate of that article.
9. Run the Scorer role with the article, candidate, anchor, rubric, routing evidence, and prior trace. Require source-grounded claim checks and a draft soft score.
10. Run the independent Reviewer role on every draft. Pass only inputs, structured decisions, cited evidence, and calculations—not hidden reasoning.
11. Keep the semantic terminals reachable here as a backstop for whatever the Grounding Gate missed. When a claim check shows a central reversal or a central fabrication, the Scorer proposes and the Reviewer confirms `FACTUAL_REVERSAL` or `FABRICATED_CONTENT` with score `0` and `terminal_rank` `0`. A wrong peripheral number or secondary entity stays a soft faithfulness penalty. The Reviewer may also escalate `OBVIOUS_TRUNCATION` here when the candidate physically stops mid-thought, since the gate proposes truncation only on provable string evidence.
12. On `REVISE`, let the Scorer revise once from explicit review findings, then review again. On unresolved disagreement, mark `LOW_CONFIDENCE` and preserve both positions.
13. Run `scripts/validate_result.py`. Do not deliver output until schema, score ranges, dimension sums, review status, and trace rules pass.
14. For five summaries per article, order terminal failure tiers first, then soft scores. Preserve evidence-backed ties.
15. Delegate the validated result to a fresh Report Agent that invokes the sibling `$generate-summary-report` skill. Provide final score JSON/JSONL, batch metadata, hard-gate drafts, embedding drafts, grounding-gate drafts, and concise audited findings when available.
16. Deliver the machine-readable result and the Report Agent's validated English Markdown report together.

## Agent execution

Use four genuinely separate Codex subagents:

- Grounding Gate Agent: decide only whether a candidate is grounded in its article. It sees the article and the candidate, never the rubric's dimensions, never the anchor, never another article, and it never produces a score.
- Scorer Agent: generate the article anchor in an article-only pass, then score candidates that cleared both hard-constraint layers.
- Reviewer Agent: independently confirm every early exit and review every soft score and cited source span.
- Report Agent: invoke `$generate-summary-report` in a fresh context to summarize validated aggregate results and deterministic charts for readers who will not inspect JSON/JSONL.

Keep the Grounding Gate and the Scorer in separate contexts. A single agent that both screens and scores will trade a central defect for a low score instead of stopping it.

Launch these roles with Codex's subagent/delegation mechanism. Passing role prompts to a local model or simulating multiple roles inside one model call does not satisfy this requirement. Scorer and Reviewer must have separate agent identities and fresh task contexts; the Report Agent must be a third role.

**Local-model prohibition:** never use Ollama or another local generative model for anchor generation, scoring, review, revision, or report conclusions. The only permitted local model is the configured embedding model used by `scripts/embedding_gate.py`. If Codex subagent delegation is unavailable, stop and report the missing capability instead of falling back to a local generator or single-agent prompt simulation.

Every Scorer and Reviewer call must include one relevant few-shot example from `references/few-shot-examples.md`. Select by stage and suspected condition. For a general soft-score call, use the closest dominant quality issue. The Report Agent reads its own `references/conclusion-example.md`. Never use evaluation targets from the current batch as few-shot examples.

## Efficiency rules

- Stop expensive work after a Reviewer-confirmed terminal failure.
- Do not embed confirmed copies, over-length outputs, or obvious truncations.
- Call a stronger relevance checker only on embedding suspects or boundary cases.
- Use a Codex Reviewer subagent, not a local reranker or local generative model, for semantic confirmation.
- Generate the anchor once per article, not once per summary.
- Reuse source chunks, embeddings, and anchors within a batch.
- Generate charts deterministically from final JSON/JSONL; do not ask the Report Agent to estimate counts or draw charts.
- Do not browse for new training or evaluation data while reporting. Treat autonomous corpus expansion as a separate, explicit future task with provenance and licensing controls.

## Scripts

- `scripts/prepare_batch.py`: join article and summary JSONL while excluding dataset-only reference summaries. `--article-corpus-output` is optional and serves offline threshold calibration; no runtime stage reads it.
- `scripts/hard_gate.py`: deterministic draft gates and trace creation for JSON or JSONL input.
- `scripts/apply_terminal_reviews.py`: apply genuine Codex Reviewer hard-gate decisions and create terminal/survivor artifacts.
- `scripts/embedding_gate.py`: **required** Ollama similarity (`qwen3-embedding:0.6b`) between a candidate and its own assigned article. Cross-article comparison is prohibited, so the script accepts no article bank and emits no rank, best-match, or margin evidence.
- `scripts/apply_relevance_reviews.py`: apply genuine Codex Reviewer off-topic decisions and create terminal/survivor artifacts.
- `scripts/validate_grounding_outputs.py`: validate Grounding Gate IDs, verdicts, categories, and cited spans, and reject any row that carries a score.
- `scripts/apply_grounding_reviews.py`: apply Reviewer grounding decisions, emit confirmed semantic terminals, and continue rejected proposals to scoring.
- `scripts/make_agent_batches.py`: split survivors into deterministic article-aligned Codex Agent batches.
- `scripts/validate_scorer_drafts.py`: validate Codex Scorer draft IDs, dimensions, anchors, labels, and trace events.
- `scripts/validate_reviewer_outputs.py`: validate independent soft-score review IDs, decisions, score suggestions, few-shot use, and traces.
- `scripts/apply_soft_reviews.py`: deterministically finalize approved drafts and isolate the single allowed revision pass.
- `scripts/validate_revised_drafts.py`: validate the Scorer's single revision pass against Reviewer requests.
- `scripts/validate_final_reviews.py`: validate the terminal Reviewer decision after the single revision pass.
- `scripts/validate_late_terminal_reviews.py`: validate terminal failures recovered by the Reviewer during soft-score audit.
- `scripts/assemble_reviewed_results.py`: merge terminal routes, approved drafts, one-pass revisions, and late terminal recoveries in original input order.
- `scripts/validate_result.py`: final schema, arithmetic, review, and trace validation.
- `scripts/rank_results.py`: rank validated results within each article while keeping off-topic last.
- `$generate-summary-report`: sibling Report Agent skill that derives audited statistics, renders fixed charts, writes the fixed-section English Markdown report, and validates the 800-word limit.

Use `python3 <script> --help` for CLI options.
