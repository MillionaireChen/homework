# Project Decision Log

This file records the main decisions that shaped the project. `progressing_GT.md` contains the current GPT/Codex implementation log. Historical Claude implementation artifacts remain under `plugin_claude/` and are not modified by the GPT work.

## 2026-08-19 — Initial Data Inspection

The supplied corpus contains 50 Japanese news articles with five candidate summaries per article, for 250 article-summary pairs. Early exploration found several recurring patterns:

- exact matches to supplied reference summaries;
- prefixes or truncated forms of reference summaries;
- direct copying from the article;
- summaries belonging to another article;
- unmarked cases containing hallucination, fine-grained factual errors, factual reversal, low coverage, incoherence, or invented commentary.

The most difficult cases are fluent hallucinations and factual reversals because they can be topically similar and stylistically convincing.

## 2026-08-19 — Reference Summary Correction

An early design used the supplied reference summary as a runtime coverage comparator and ranking anchor. The user correctly rejected this approach: a real production request contains only the source article and a generated candidate.

Final rule:

- runtime scoring must depend only on `(article, candidate_summary)`;
- reference summaries may support offline exploration or validation;
- reference-derived matches must never become a required runtime feature or automatic score.

This correction changed the architecture from a reference-based ensemble to a reference-free funnel.

## 2026-08-19 — Deterministic First, Semantic Later

The user proposed a cascade that removes obvious failures before expensive model judgment. The accepted order is:

1. deterministic string and structure checks;
2. embedding-based relevance nomination;
3. semantic confirmation of possible off-topic content;
4. claim-grounded soft scoring;
5. independent review;
6. validation, ranking, and reporting.

This order reduces token use and latency while retaining more expensive reasoning for ambiguous candidates.

## 2026-08-19 — Copy Detection

Near-verbatim copying should be detected with physical text comparison, not embeddings. Useful signals include normalized containment, longest common substring, and character or n-gram coverage.

The earlier idea of a 25% penalty was not supported by the assignment and was withdrawn. A confirmed whole-summary source copy is treated as failure to perform the summarization task. It receives score `0`, a copy-specific ranking tier, and an early stop. Shared entities, numbers, and short phrases remain legal.

## 2026-08-19 — Sentence Count and Truncation

The product specification requires three sentences or fewer. The final implementation treats a Reviewer-confirmed over-length candidate as a terminal failure while preserving a distinct rank tier.

Truncation requires stronger evidence than missing punctuation. High-confidence signs include a dangling conjunction, an incomplete grammatical ending, or unbalanced quotation marks or brackets. A Reviewer confirms every proposed truncation because deterministic rules can miss unpunctuated fragments or flag legitimate short headlines.

## 2026-08-19 — Relevance Gate

Embeddings are suitable for identifying potentially unrelated summaries after deterministic failures have been removed. They are not suitable for judging summary quality: copied, hallucinated, and factually reversed candidates can all remain highly similar to the article.

In a batch, the gate compares the candidate with its assigned article and other articles. Own-article rank and similarity margin provide strong nomination evidence. In a single-pair request, absolute similarity is only a warning because there is no comparative corpus.

No embedding signal is terminal by itself. A semantic Reviewer confirms whether the candidate is actually unrelated.

### Relevance calibration experiments

Two experiments tested valid reference summaries against mismatched summaries:

| Experiment | Valid reference mean | Unrelated mean | Observed gap |
|---|---:|---:|---:|
| 10 articles with curated unrelated summaries | 0.800 | 0.275 | 0.313 |
| 10 new articles with random cross-article summaries, seed 42 | 0.780 | 0.263 | 0.343 |

Across these 20 articles, valid examples were above roughly `0.70` and mismatches below roughly `0.40`. This supports `0.50` as a corpus-specific starting threshold. It does not eliminate the need for calibration or review.

## 2026-08-19 — Hard and Soft Constraints

Hard constraints determine whether a candidate qualifies for soft scoring:

- empty output;
- more than three sentences;
- near-verbatim source copy;
- obvious truncation;
- completely unrelated content.

Soft constraints create a quality gradient among survivors:

- faithfulness, including hallucination and reversal;
- coverage of the main event and key facts;
- coherence and grammatical completeness;
- conciseness.

Terminal failures receive score `0` but retain separate rank tiers. This supports the user’s requirement to order five candidates rather than collapsing every failure into an indistinguishable bucket.

## 2026-08-19 — Scorer and Reviewer Roles

The user required two independent agents:

- the Scorer produces a structured article anchor, claim checks, dimension scores, and a draft result;
- the Reviewer confirms every early exit and independently audits the source evidence, score, label, and arithmetic.

Every role call receives exactly one matching few-shot case. If the Reviewer requests a revision, the Scorer may revise once and the result is reviewed again. Unresolved disagreement is preserved explicitly.

The trace records the actual path taken, including recovered failures that deterministic gates missed.

## 2026-08-19 — Claude Plugin Milestone

A separate Claude implementation was created under `plugin_claude/summary-quality-funnel/` and tested on a 25-pair sample. It demonstrated hard-gate routing, soft scoring, Reviewer correction, and ranking. One important case showed the value of two layers: the soft-stage Reviewer recovered an unpunctuated truncation missed by the deterministic rule.

The GPT/Codex implementation must remain independent and must not edit the Claude plugin.

## 2026-08-20 — GPT/Codex Plugin and 50-Pair Experiment

The GPT/Codex implementation lives under `plugin_GPT/summary-quality-funnel/`. It contains reference-free hard-gate, embedding, validation, ranking, prompt, rubric, and schema components.

A 50-pair experiment demonstrated the basic cascade without using reference summaries at runtime. It confirmed that deterministic copy detection can remove clear failures before embeddings and that relevance evidence can nominate cross-article mismatches.

## 2026-08-20 — Random 20-Pair End-to-End Run

A reproducible seed-42 run selected 20 pairs covering 14 unique articles.

- 12 completed soft scoring.
- 8 terminated: 5 copies, 2 truncations, and 1 off-topic candidate.
- 3 final records required revision.
- all 20 final records received Reviewer approval.
- soft-score mean was 76.08, median 76, and range 43–98.

The run caught fluent but factually wrong summaries and produced valid ranking records. It supports the conclusion that the pipeline is a usable prototype requiring broader validation.

## 2026-08-20 — Anchor Embedding Ablation

The user proposed embedding the candidate against the generated anchor in addition to the full article.

The small ablation produced mixed results:

- coverage Spearman correlation: article `0.5282`, anchor `0.6303`;
- leave-one-out coverage MAE: article `3.6246`, anchor `4.0123`, combined `4.4121`.

The anchor remains useful as a structured coverage checklist for the Scorer. Anchor similarity is not added as a gate or scoring feature because predictive error did not improve and anchor generation increases cost.

## 2026-08-20 — Formal Report Agent

The user requested a third role so that readers do not need to inspect JSONL.

The GPT plugin now exposes `$summary-quality-funnel:generate-summary-report` as an independent skill. It receives only validated score artifacts and audited findings, generates deterministic charts and statistics, writes an English report with four fixed sections, and enforces an 800-word limit.

The Report Agent cannot rescore candidates, inspect reference summaries, browse for new data during reporting, or claim production readiness from a small sample. Autonomous corpus expansion remains a separate future project with explicit authorization, provenance, licensing, deduplication, and evaluation requirements.

## Current Status

The current design has three isolated roles—Scorer, Reviewer, and Report Agent—and a deterministic-to-semantic cascade with early stopping. The next work is broader held-out validation, controlled factual perturbations, human ranking comparison, and threshold recalibration across models and domains.

All project-facing material is English. Japanese source articles, candidate summaries, evidence spans, and language-specific fixtures remain Japanese because they are the evaluated data rather than documentation.
