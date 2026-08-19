# Progressing GT — Independent Decision and Implementation Log

This file records the GPT/Codex implementation. It does not modify the Claude plugin. The production objective is a reference-free quality funnel that accepts only an article and a candidate summary.

## 2026-08-19 — Hard and Soft Constraints

The assignment requires summaries of three sentences or fewer. The design separates failures that can be detected with deterministic evidence from quality judgments that require semantic reasoning.

Runtime inputs:

- article text;
- candidate summary;
- optional article and summary identifiers.

`reference_summary` is excluded from runtime evaluation. It may be used only for offline research and never as a production comparator, hidden label, or automatic high-score anchor.

### Hard constraints

1. **Empty output.** Deterministic terminal failure.
2. **More than three top-level sentences.** Deterministic product-specification failure. Japanese sentence counting must ignore punctuation inside balanced quotations.
3. **Near-verbatim source copy.** Use Unicode normalization, containment, longest common substring, and character or n-gram coverage. Embeddings are inappropriate because copied text is necessarily semantically similar.
4. **Obvious truncation.** Use incomplete endings, dangling conjunctions, and unbalanced quotation or bracket evidence. Missing final punctuation alone is not enough.
5. **Completely unrelated content.** Embeddings nominate suspects; an independent semantic Reviewer confirms or rejects the terminal decision.

Confirmed terminal failures receive score `0`, but separate ranking tiers preserve ordering: off-topic `0`, copy `1`, truncation `2`, and over-length `3`.

### Soft constraints

Only survivors receive a continuous quality score:

- faithfulness: 0–50;
- coverage: 0–30;
- coherence: 0–15;
- conciseness: 0–5.

The source article is authoritative. A generated anchor may help organize coverage, but it is not a reference answer and cannot validate facts.

## 2026-08-19 — Funnel Order and Cost Control

The execution order is:

```text
article + candidate
  -> deterministic gate proposals
  -> independent gate review
  -> optional embedding relevance nomination
  -> independent relevance review
  -> article-only anchor generation
  -> claim-grounded soft scoring
  -> independent score review
  -> schema validation and ranking
  -> independent report generation
```

The pipeline stops after a confirmed terminal failure. It does not spend tokens generating an anchor or scoring a candidate that already failed. Article embeddings, anchors, and chunks are cached within a batch.

## 2026-08-19 — Copy Policy Correction

The assignment does not specify a 25% plagiarism penalty. That value came from an earlier design discussion and was removed.

Current policy: if the whole candidate is confirmed as an exact or near-exact continuous copy of the article, it has not performed the requested summarization task. It therefore receives terminal label `VERBATIM_SOURCE_COPY`, score `0`, rank tier `1`, and an early stop. Local factual overlap is allowed and must not trigger this rule.

## 2026-08-19 — Relevance Experiments

Two independent 10-article experiments compared each article with a valid reference and with an unrelated summary.

| Experiment | Matched range / mean | Mismatched range / mean | Separation |
|---|---|---|---:|
| Curated unrelated set | 0.711–0.868 / 0.800 | 0.163–0.398 / 0.275 | 0.313 |
| Random cross-article set, seed 42 | 0.707–0.858 / 0.780 | 0.164–0.364 / 0.263 | 0.343 |

The result supports an initial relevance threshold near `0.50` for this model and corpus. It does not prove a universal constant. Model, language, domain, and distribution changes require recalibration. Similarity separates topic mismatch; it does not detect hallucination, reversal, or overall quality.

## 2026-08-19 — Independent GPT Plugin

The Codex implementation was created under `plugin_GPT/summary-quality-funnel/`. No file under `plugin_claude/` is edited by this work.

The evaluation skill contains:

- deterministic hard-gate scripts;
- an optional Ollama embedding gate;
- a structured rubric and stage-specific few-shots;
- isolated Scorer and Reviewer prompts;
- result validation and ranking scripts.

The plugin is reference-free at runtime and preserves an auditable trace for every result.

## 2026-08-20 — Random 20-Pair End-to-End Run

A seed-42 sample of 20 article-summary pairs covering 14 unique articles was passed through the pipeline.

- 12 candidates completed soft scoring.
- 8 candidates terminated early: 5 copies, 2 truncations, and 1 off-topic result.
- 5 terminal proposals originated in the deterministic gate.
- 2 additional hard failures were recovered downstream.
- all 20 final records were approved by the Reviewer;
- 3 records required at least one revision;
- soft scores ranged from 43 to 98, with mean 76.08 and median 76.

The run showed that the cascade can route clear failures, distinguish fluent factual errors from good summaries, recover missed hard failures, and produce valid machine-readable records. The evidence supports a **usable prototype that needs broader validation**, not production readiness.

## 2026-08-20 — Anchor Embedding Ablation

The user proposed comparing candidate-to-article embeddings with candidate-to-generated-anchor embeddings.

On the random 20-pair run, anchor similarity had a higher Spearman correlation with coverage than article similarity (`0.6303` versus `0.5282`). However, leave-one-out coverage prediction had lower mean absolute error with article similarity alone (`3.6246`) than with anchor similarity alone (`4.0123`) or both features (`4.4121`).

Decision: keep the generated anchor for structured coverage reasoning, but do not add anchor embedding as a gate or score feature yet. The evidence is mixed, the sample is small, and anchor generation adds model cost.

## 2026-08-20 — Formal Report Agent

The initial implementation embedded reporting instructions inside the evaluation skill. That was not a genuinely independent Report Agent.

The plugin now exposes a second first-class skill:

```text
$summary-quality-funnel:generate-summary-report
```

It owns:

- its own `SKILL.md` and Codex UI metadata;
- a dedicated report few-shot;
- a deterministic statistics and chart script;
- an English report validator;
- a strict four-section, under-800-word output contract.

The evaluation skill delegates only validated records and audited findings to this fresh role. The Report Agent does not rescore candidates, estimate counts, inspect reference summaries, browse for data, or claim production readiness from a small run.

## Language Policy

Project-facing documentation, prompts, labels, reports, charts, and code messages are English. Japanese source articles, candidate summaries, evidence spans, and language-specific fixtures remain Japanese because translating them would change the evaluation task.

## Next Validation Work

- Run article-level held-out evaluation.
- Add controlled perturbations for numbers, entities, negation, causality, and truncation.
- Measure within-article ranking agreement against human labels.
- Measure precision and recall for each terminal failure mode.
- Recalibrate the embedding relevance gate across models and domains.
- Treat autonomous web corpus expansion as a separate, explicitly authorized project with provenance and licensing controls.
