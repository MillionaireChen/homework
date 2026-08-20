# Summary Quality Evaluation Funnel

This document describes the current design for evaluating Japanese news summaries. The production path is reference-free: it accepts only an article and a candidate summary.

## 1. Objective

Input: one `(article, candidate_summary)` pair, with optional identifiers.

Output: a validated score record containing:

- a terminal failure or a 0–100 soft-quality score;
- dimension scores for faithfulness, coverage, coherence, and conciseness;
- a quality label and within-article ranking tier;
- an auditable trace of each stage visited;
- an independent Reviewer decision.

The evaluator must remain useful when no gold or reference summary exists. Reference summaries may support offline research, but they never enter the runtime scoring path.

## 2. Design Principles

1. Apply cheap, deterministic checks before semantic or generative models.
2. Separate hard constraints from soft quality judgments.
3. Treat embeddings as relevance evidence, never as a quality score.
4. Require independent review for every proposed early exit and every soft score.
5. Preserve routing state, evidence, and corrections in the output.
6. Generate human-readable reports from validated machine output, not from memory or estimates.

## 3. Funnel Architecture

### Stage A: Deterministic hard-gate proposals

The rule layer checks:

- empty output;
- more than three top-level sentences;
- near-verbatim copying from the article;
- obvious syntactic truncation.

These rules propose a route. A Reviewer confirms or rejects each proposed hard exit. Confirmed terminal cases receive a score of `0` and a separate ranking tier so that different failure modes remain sortable.

Hard constraints form two layers. Layer 1 is physical and provable by a script; layer 2 is semantic and only an agent can judge it.

Recommended terminal ordering, from worst to least severe:

1. `FACTUAL_REVERSAL`, `FABRICATED_CONTENT`, `OFF_TOPIC` — rank `0`;
2. `VERBATIM_SOURCE_COPY` — rank `1`;
3. `OBVIOUS_TRUNCATION` — rank `2`;
4. `OVER_SENTENCE_LIMIT` — rank `3`.

The three rank-`0` categories share the worst tier because each of them makes the output unusable rather than merely flawed, and a summary that states the opposite of its source, or invents its central content, misleads a reader who cannot check the article.

Local overlap, shared entities, dates, or fixed news phrases are not sufficient evidence of copying. Missing normal final punctuation is a reproducible truncation warning, not an automatic final decision; the Reviewer confirms whether the candidate physically ends mid-thought.

### Stage B: Embedding relevance nomination

Compare the candidate with its own assigned article and with nothing else. A production request supplies one article and one candidate, so own-article rank against a corpus and margin to other articles are inadmissible: they consume context the caller never provided. Absolute similarity below the calibrated threshold is a cheap hint that the next stage should look closely.

Embedding evidence never causes a terminal decision by itself. This protects topical but factually wrong summaries from being misclassified as relevant and protects unusual but valid summaries from being discarded.

### Stage B2: Grounding gate, the semantic hard constraint

Embeddings and string rules both fail on the most dangerous candidate: fluent, on topic, correct length, no copying, and asserting the opposite of the article or inventing its central content. Similarity stays high precisely because the subject matter is right.

A dedicated Grounding Gate Agent therefore screens every survivor before any scoring, answering one question: is this candidate grounded in the supplied article? It returns `NOT_GROUNDED` with exactly one central category — `OFF_TOPIC`, `FACTUAL_REVERSAL`, or `FABRICATED_CONTENT` — and cites one article span plus one candidate span. It never assigns a score, never sees the anchor, and never sees another article.

The Reviewer then confirms or rejects. A confirmed proposal terminates at `0` before anchor generation; a rejected proposal continues to scoring with both positions in the trace. The gate is deliberately blind to quality, because an agent that both screens and scores will trade a central defect for a low score instead of stopping it.

Centrality is the boundary that keeps this from swallowing the whole rubric: a wrong peripheral number, a wrong secondary entity, or one unsupported added detail is `GROUNDED` and loses faithfulness points during scoring.

The soft-scoring stage keeps the same two semantic terminals reachable as a backstop, since a gate can miss what a claim-by-claim audit later exposes.

Two offline experiments covering 20 articles found a wide separation between valid references and randomly mismatched summaries: valid similarities stayed above roughly `0.70`, while mismatches stayed below roughly `0.40`. A threshold near `0.50` is therefore a useful engineering starting point for this corpus, not a universal constant.

### Stage C: Article-only anchor generation

The Scorer produces a structured article anchor before seeing candidates:

- main event;
- key facts;
- a concise anchor summary.

The anchor supports coverage reasoning only. It is not a gold answer and cannot override the source article. One anchor is cached per article.

An anchor-embedding ablation showed mixed evidence: anchor similarity correlated more strongly with coverage on one small sample, but leave-one-out prediction error did not improve. Anchor embeddings therefore remain diagnostic rather than a scoring or gating feature.

### Stage D: Soft scoring

Only candidates that pass all terminal gates qualify for soft scoring.

| Dimension | Range | Primary question |
|---|---:|---|
| Faithfulness | 0–50 | Are all candidate claims supported by the article? |
| Coverage | 0–30 | Does the candidate capture the main event and important facts? |
| Coherence | 0–15 | Is it complete, grammatical, and logically ordered? |
| Conciseness | 0–5 | Is it compact without unnecessary repetition? |

The Scorer decomposes the candidate into atomic claims, cites article evidence, assigns dimension scores, and calculates the total exactly. Semantic similarity cannot compensate for contradiction, hallucination, or factual reversal.

### Stage E: Independent review

The Reviewer independently checks:

- every hard-gate proposal;
- every off-topic nomination;
- claim-to-source evidence;
- dimension arithmetic and label boundaries;
- whether the trace matches the route actually taken.

A `REVISE` decision permits one Scorer revision followed by a second review. Unresolved disagreement is preserved as `LOW_CONFIDENCE`; it is not silently averaged away.

### Stage F: Report Agent

The dedicated Report Agent receives deterministic statistics derived from validated score JSON or JSONL. The reporting code produces:

- deterministic funnel and score charts;
- Sections 1–3 and the fixed English Markdown layout under 800 words;
- four fixed sections: input data, funnel outcomes, results, and conclusion;
- a validated report artifact.

The Report Agent may author only the conclusion, capped at 120 words, and must distinguish prototype evidence from production validation. It cannot write the numbered sections, invent or manually recalculate statistics, or edit charts. Corpus expansion and web collection are separate future capabilities requiring explicit authorization, provenance, licensing review, deduplication, and a new evaluation protocol.

## 4. Agent Boundaries

- **Grounding Gate Agent:** decides only whether a candidate is grounded in its article. No score, no anchor, no other article.
- **Scorer Agent:** creates the article anchor and drafts the soft score.
- **Reviewer Agent:** confirms every early exit, including grounding-gate proposals, and audits every score.
- **Report Agent:** writes only a short conclusion from fixed validated statistics; code generates the rest of the report.

Each role uses a fresh context. Grounding Gate, Scorer, and Reviewer calls receive exactly one condition-matched few-shot example. The Report Agent uses its own report example rather than scoring examples.

## 5. Efficiency and Early Stopping

Confirmed terminal failures stop before expensive stages. The system does not embed confirmed copies, score confirmed truncations, or generate anchors for candidates that cannot qualify for soft scoring. Within a batch, article embeddings, source chunks, and anchors are cached.

This cascade reduces model calls and latency while keeping deterministic failures explainable. The Reviewer remains mandatory because a cheap detector can still be confidently wrong at a boundary.

## 6. Validation Strategy

Validation has four layers:

1. script and schema tests for every stage;
2. controlled cases for copy, truncation, over-length, off-topic, contradiction, low coverage, incoherence, and verbosity;
3. article-level held-out evaluation and perturbation tests;
4. human comparison using ranking agreement and failure-mode precision/recall.

Small random runs establish whether the pipeline executes coherently and catches known failure types. They do not establish production readiness. Thresholds must be recalibrated when the embedding model, language, domain, or article distribution changes.

## 7. Current Evidence

- A 50-pair reference-free funnel experiment demonstrated deterministic copy detection and embedding-based off-topic nomination.
- Two independent 10-article relevance experiments reproduced a large similarity gap between matched and mismatched summaries.
- A random 20-pair end-to-end run exercised all three roles, terminal routing, soft scoring, revision, validation, charts, and report generation.
- A full 250-pair run covered all 50 articles: 82 terminal results, 168 reviewed soft scores, 20 one-pass revisions, and no unresolved escalations.
- The current conclusion is: **a functioning audited pipeline with evidence on this dataset, not a production-accuracy guarantee**.

## 8. Deliverables

- `plugin_GPT/summary-quality-funnel/`: Codex plugin with evaluation and report skills.
- `experiments_GPT/`: reproducible exploratory and ablation outputs.
- `evaluation_runs_GPT/`: audited end-to-end score records and reports.
- `progressing_GT.md`: GPT-side decision and implementation log.

Japanese text inside datasets, evaluated articles, candidate summaries, evidence spans, and language-specific fixtures is intentionally preserved. All project-facing documentation, prompts, labels, reports, and visualizations are English.
