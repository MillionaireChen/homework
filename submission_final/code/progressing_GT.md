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
4. **Obvious truncation.** Use incomplete endings, dangling conjunctions, unbalanced quotation or bracket evidence, and missing normal sentence-final punctuation. The deterministic layer only proposes this route; the Reviewer must still confirm physical truncation from the text.
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
- a dedicated conclusion example;
- deterministic statistics, chart, and Markdown-generation scripts;
- an English report validator;
- a strict four-section, under-800-word output contract.

The evaluation skill delegates only validated records and audited findings to this fresh role. Code generates Sections 1–3, every statistic, both charts, and the final Markdown layout. The Report Agent may write only a conclusion of at most 120 words. It does not rescore candidates, estimate counts, inspect reference summaries, browse for data, or claim production readiness from a small run.

## 2026-08-20 — Full 250-Pair Codex-Agent Evaluation

The complete dataset of 50 articles and 250 candidate summaries was evaluated without runtime reference summaries and without a local generative model. Local inference was restricted to the configured embedding model; genuine Codex Scorer, Reviewer, and Report Agents handled anchors, scoring, review, revision, and the conclusion.

- 53 candidates were stopped by Reviewer-confirmed initial hard gates: 50 verbatim copies and 3 obvious truncations.
- Embeddings nominated 19 off-topic suspects; the Reviewer confirmed 16 and rejected 3.
- 181 candidates entered soft scoring.
- The score Reviewer directly approved 148 drafts, requested one revision for 20, and recovered 13 additional physical truncations.
- All 20 revised drafts passed a final review; no result remained escalated.
- The final file contains 82 terminal results and 168 soft scores across exactly 50 five-candidate article groups.
- Terminal results comprise 50 source copies, 16 off-topic candidates, and 16 obvious truncations.
- Final soft scores have mean 80.43, median 85, range 32–100, and labels: 65 EXCELLENT, 49 GOOD, 42 MIXED, and 12 POOR.

The recovered truncations exposed a deterministic blind spot: candidates ending mid-phrase without a comma or unmatched delimiter had passed the original gate. The plugin now nominates any candidate lacking normal sentence-final punctuation for truncation review. This change increases review traffic but prevents those cases from consuming anchor and scoring work in future runs.

## 2026-08-20 — Reference Access Granted to the Report Agent Only

The previous report skill forbade any contact with `reference_summary`. That rule was correct for runtime and wrong for reporting: it also blocked the only offline comparator available, so the report could publish detection counts with no denominator and no accuracy figure.

New policy: the Report Agent is the single role permitted to read `reference_summary`, and only after every score is final. Reporting is offline, so a reference read there cannot influence a score. Every runtime stage stays reference-free, no score may be recomputed after a reference is read, and the report must present the outcome as agreement with weak labels rather than validated accuracy.

`scripts/reference_validation.py` derives one planted category per candidate from the corpus alone, then joins the score file, so no evaluator output can affect a label:

- candidate contained in its own article: continuous source copy;
- candidate equal to its reference: reference reproduction;
- candidate a leading fragment of its reference: truncation;
- candidate matching a different article: off-topic;
- everything else: generated, no derivable label.

On the full 250-pair run this labels 141 candidates and leaves 109 unlabelled.

- reference reproductions: 58, all 58 survived scoring, mean 83.29, range 44-98;
- continuous source copies: 50, all 50 terminal;
- truncated references: 17, 16 terminal, 1 missed (`51395937_e409196f`, scored 74);
- other-article summaries: 16, all 16 terminal;
- agreement on labelled candidates: 140 of 141;
- articles where a planted failure scored at or above the reference: 0 of 50.

The report now carries this as Section 4 with the conclusion moved to Section 5. Supplying the corpus pair is optional; without it the four-section report is unchanged. Two limits are stated in the report itself: reference reproductions are assumed acceptable although the corpus references are uneven, and the 109 generated candidates that carry the fluent factual errors remain unlabelled. Reference reproductions are also not the best candidate in their article: a generated candidate outscored the reference in 44 of 50 articles, because the evaluator credits only facts present in the article body.

## 2026-08-20 — Cross-Article Evidence Is Inadmissible at Runtime

The user rejected the relevance gate's batch comparison, and the objection is correct. A production request carries one article and one candidate. Comparing that candidate with other articles in the same batch consumes context the caller never supplied, and comparing it with a stored corpus is not permitted by the business rule. Own-article rank, best-match article identifier, and margin against the best other article are therefore inadmissible runtime evidence.

`OTHER_ARTICLE` is likewise not a runtime category. The runtime vocabulary has only unrelated content, established from the article and the candidate alone.

The defect is real and it reached the shipped artifacts: `embedding_drafts.jsonl` records `mode: multi_article_retrieval`, and every row carries `assigned_rank`, `best_match_article_id`, and `margin_vs_best_other`.

Measured impact on the full 250-pair run: none.

- All 16 confirmed off-topic candidates were also nominated by the single-pair absolute rule, with assigned similarity between 0.1303 and 0.4813 against a 0.50 threshold.
- No candidate was nominated by relative evidence alone.
- All 19 nominations and all 16 confirmations would be unchanged with the cross-article comparison removed.

The single-pair signal is weak by itself and must stay non-terminal. The three rejected suspects sat at 0.4034, 0.4585, and 0.4939, inside the same band as genuine off-topic cases reaching 0.4813. Absolute similarity only nominates; the semantic Reviewer, which rejected all three, performs the actual judgment.

Required changes:

- the embedding gate defaults to single-pair mode, and `multi_article_retrieval` leaves the runtime path entirely;
- `assigned_rank`, `best_match_article_id`, and `margin_vs_best_other` are neither produced nor read at runtime, and may survive only inside explicitly labelled offline calibration output;
- the skill, rubric, and calibration notes stop presenting batch rank and margin as nomination evidence;
- the offline reference cross-check keeps its other-article label, because there it records the provenance of planted test data for a finished run rather than a runtime capability.

Any future claim about off-topic recall must be measured in single-pair mode, since batch mode overstates the evidence a production caller can provide.

### Resolution: one off-topic category, terminal, judged from the pair alone

Two corrections came from the user.

First, there is no such category as a summary belonging to another article. Whatever its origin, a candidate unrelated to the article in front of us is off-topic and nothing else. `OTHER_ARTICLE` was renamed to `OFF_TOPIC` in the offline cross-check, described as unrelated to its assigned article, and the corpus scan that finds those candidates is documented as an offline labelling method rather than a category of its own.

Second, a confirmed off-topic candidate keeps score `0`. Awarding coherence and conciseness points to a summary about a different event was rejected: a text that does not summarize the supplied article has not performed the task, so no partial credit applies and the existing terminal rank tiers stay.

Only the route to that judgment changed. Relatedness is now decided from the article and the candidate alone:

- `scripts/embedding_gate.py` compares a candidate with its own assigned article, accepts no article bank, and emits `mode: assigned_article_only` with no rank, best-match, or margin field;
- `scripts/prepare_batch.py` still writes an article corpus, but the flag is optional and documented as offline threshold calibration that no runtime stage reads;
- the skill workflow and the calibration reference were corrected, and the calibration note records the overlapping similarity band that makes Reviewer confirmation mandatory.

The rewritten gate was checked offline with deterministic fake vectors: same-topic pairs score high, an unrelated candidate is nominated, and none of the four prohibited evidence fields appears in the output.

The shipped `embedding_drafts.jsonl` from the 250-pair run keeps its original `multi_article_retrieval` evidence. It records what actually ran, and rewriting it would misrepresent the run. Future runs use the corrected gate.

## 2026-08-20 — New Terminal Failure: FACTUAL_REVERSAL

Cross-checking the 109 unlabelled candidates exposed a failure mode with no rule of its own. A candidate can be fluent, within the sentence limit, not a copy, not truncated, on topic, and still assert the opposite of the article: the offensive was halted when it was launched, the rescued boys were gravely weakened when the video showed them healthy, the airline will continue the tests it actually suspended, the cabinet stayed when it resigned.

Nothing upstream can catch this. The deterministic gates pass it because the string evidence is clean. The embedding gate passes it because the topic is correct and similarity stays high. It reaches soft scoring by design, which is precisely the reason the scoring agents exist, and until now it only lost faithfulness points there.

The user ruled that a reversal receives `0`. A summary asserting the opposite of its source has not summarized it.

New terminal category `FACTUAL_REVERSAL`:

- terminal, score `0`, `terminal_rank` `0`, label `HARD_FAIL_REVERSAL`;
- raised only by the Scorer's claim checks or the Reviewer's audit, and confirmed by independent review; no deterministic gate and no embedding may propose it;
- scoped to the central fact: a negated main event, an inverted outcome, an inverted state, or an inverted decision, judged against the anchor's `main_event`;
- a wrong peripheral number, a wrong secondary entity, an added unsupported detail, or a reversed minor sub-claim stays inside soft scoring as a faithfulness penalty.

The scope line is the load-bearing part. Without it every wrong figure would collapse to `0` and the soft gradient would disappear.

Ranking decision: `FACTUAL_REVERSAL` joins the worst tier at rank 0 next to `OFF_TOPIC` and `EMPTY_OUTPUT` rather than renumbering the existing tiers. A summary that states the opposite of the article misleads a reader who cannot check the source, so it is at least as harmful as one that is merely irrelevant, and it must never outrank a truncated or copied candidate. Keeping the existing numbers also leaves the finished 250-pair run comparable.

Files changed in `plugin_GPT/summary-quality-funnel/skills/evaluate-summary-quality/`: `references/rubric.md`, `references/agent-prompts.md`, `references/few-shot-examples.md`, `references/output-schema.md`, `SKILL.md`, `scripts/validate_result.py`, `scripts/assemble_reviewed_results.py`, `scripts/validate_late_terminal_reviews.py`. The deterministic-gate applier was deliberately left alone so the category cannot originate there.

One few-shot example was added, `FACTUAL_REVERSAL`, showing a fluent on-topic candidate that inverts a state-of-emergency decision. The existing `FACTUAL_ERROR` example had to be re-cut: it reversed a central fact (`10人が軽傷` scored as `10人が死亡`) while being labelled a soft `POOR`, which the new rule contradicts. It now carries a wrong construction cost instead, so the bank draws a clean line between a peripheral error that keeps scoring and a central reversal that stops it.

Verification: `scripts/validate_result.py` accepts a well-formed `FACTUAL_REVERSAL` record and rejects the same record with `terminal_rank: 2`.

Not yet done: the 250-pair run was scored before this rule existed, so its 42 MIXED and 12 POOR records still contain reversals that would now terminate. Re-running the affected candidates under the new rule is open work, and the current report's score distribution must be read as pre-rule.

## 2026-08-20 — Grounding Gate Agent: Hard Constraints Become Two Layers

The `FACTUAL_REVERSAL` rule was routed through soft scoring, which the user rejected. A candidate that ignores the facts outright should not wait for a scoring pass to be caught. Hard constraints are now explicitly two layers:

- **Layer 1, physical.** Empty output, sentence count, verbatim copy, obvious truncation. A script proves these.
- **Layer 2, semantic.** A dedicated Grounding Gate Agent, running on every survivor before any scoring, and the last line of defence.

The gate answers exactly one question: is this candidate grounded in the supplied article? It returns `NOT_GROUNDED` with one central category and cites one article span plus one candidate span:

- `OFF_TOPIC`: unrelated subject;
- `FACTUAL_REVERSAL`: asserts the opposite of the main event, outcome, state, or decision;
- `FABRICATED_CONTENT`: the central event, outcome, attributed quotation, or load-bearing figure appears nowhere in the article.

`FABRICATED_CONTENT` is new in this entry, at rank 0 with label `HARD_FAIL_FABRICATION`.

Isolation rules for the gate:

- it never assigns a score, dimensions, or a quality label, and `validate_grounding_outputs.py` rejects any row that tries;
- it never receives the anchor or the soft rubric;
- it never sees an article other than the one supplied;
- it runs in its own context, separate from the Scorer, because one agent that both screens and scores will trade a central defect for a low score instead of stopping it.

Every proposal goes to the Reviewer's new grounding pass. Confirmed means score `0`, `terminal_rank` `0`, stop before anchor generation. Rejected means scoring continues with both positions preserved in the trace. The gate alone can never terminate.

Centrality remains the load-bearing boundary. A wrong peripheral number, a wrong secondary entity, one unsupported added detail, or a defect in a minor sub-claim is `GROUNDED`, and scoring penalizes it as before. Without that line the gate would swallow the rubric and every wrong figure would collapse to `0`.

The soft-scoring stage keeps both semantic terminals reachable as a backstop, since a claim-by-claim audit can expose what the gate missed.

Embedding's role shrinks accordingly: similarity below threshold is now a cheap hint that the gate should look closely, not a nomination mechanism of its own.

New scripts under `plugin_GPT/.../evaluate-summary-quality/scripts/`: `validate_grounding_outputs.py` and `apply_grounding_reviews.py`. Updated: `references/rubric.md`, `references/agent-prompts.md`, `references/few-shot-examples.md`, `references/output-schema.md`, `SKILL.md`, `scripts/validate_result.py`, `scripts/assemble_reviewed_results.py`, `scripts/validate_late_terminal_reviews.py`, and root `DESIGN.md`. One few-shot example was added for `FABRICATED_CONTENT`, and the `FACTUAL_REVERSAL` example was re-expressed as a gate verdict because the gate now owns that route.

Verification with a four-row fixture: the validator accepted a well-formed gate file and rejected a row carrying `score` and `dimensions`; the applier confirmed two proposals into terminals with rank 0, rejected a peripheral-error over-reach and continued it to scoring with both trace events, and the resulting terminal records passed `validate_result.py`.

The agent count rises from three to four: Grounding Gate, Scorer, Reviewer, Report.

Still open: the finished 250-pair run predates both layers, so its 42 MIXED and 12 POOR records contain reversals and fabrications that would now terminate. Its score distribution must be read as pre-rule until those candidates are re-run.

## 2026-08-20 — New Soft Label: FINE

The user added a fifth soft label between `MIXED` and `GOOD`.

The old `50-74` band was doing two jobs. Its upper half held candidates that are usable with one visible gap, such as a missing secondary fact or a minor unsupported detail; its lower half held candidates a reader should not rely on. Both surfaced as `MIXED`, which hid the difference exactly where a reader has to decide whether an output is shippable.

New bands:

| Label | Range |
|---|---|
| `EXCELLENT` | 90-100 |
| `GOOD` | 75-89 |
| `FINE` | 65-74 |
| `MIXED` | 50-64 |
| `POOR` | 0-49 |

`FINE` splits the old `MIXED` band at 65 rather than shifting the neighbours, so the `GOOD`, `EXCELLENT`, and `POOR` boundaries and every score already assigned stay valid. No dimension maxima and no arithmetic change.

Updated: `references/rubric.md`, `scripts/validate_scorer_drafts.py`, `scripts/validate_revised_drafts.py`, the report skill's `generate_report.py` label order, and `make_report_charts.py` label colours. The `LOW_COVERAGE` few-shot example scores 73 and was relabelled from `MIXED` to `FINE`, since a stale example would teach the wrong band.

Two gaps in the report generator were fixed in the same pass: its terminal vocabulary and chart colours did not yet include `FACTUAL_REVERSAL` or `FABRICATED_CONTENT`, so a future run using the Grounding Gate would have rendered them as unlabelled bars.

Label inventory is now 7 terminal categories and 5 soft labels.

Effect on the finished 250-pair run, if its labels were re-derived from the stored scores: 26 of the 42 `MIXED` records become `FINE`, leaving 16 `MIXED`. `EXCELLENT` 65, `GOOD` 49, and `POOR` 12 are unchanged, and no other label would move. The run's stored labels were left as they are, because that file records what the agents actually emitted; re-deriving them is a one-line change whenever the run is refreshed.

## 2026-08-20 — Where the Truncation Judgment Belongs

### Correction to the earlier record

An earlier entry stated that the plugin "now nominates any candidate lacking normal sentence-final punctuation for truncation review", implying that rule is how the 250-pair GPT run reached 16 of 17 truncations. Tracing the artifacts shows otherwise. That run's deterministic gate proposed only 3 truncations, exactly as the Claude run did. The other 13 were recovered later by the soft-score Reviewer escalating to `OBVIOUS_TRUNCATION`, along the trace path `soft_score_review -> terminal_review -> early_stop`, recorded in the 13 `late_terminal_reviews` files. The extra gate rule was added after that run and has never executed in any run.

So the two implementations were never actually different in behaviour here. The difference in the Claude run's cross-check score came from the orchestration: the soft-score Reviewer was instructed to escalate only `FACTUAL_REVERSAL` or `FABRICATED_CONTENT`, so the recovery path that produced the GPT run's 13 was closed. Four separate Reviewer agents identified truncated candidates during the run and correctly declined to act, saying truncation was outside their escalation scope. The capability was present; only the permission was missing.

### The question

Should a string test decide whether a candidate stops mid-thought?

The alternative already in the GPT code proposes a terminal on any suspicion, including a final character that is not sentence-final punctuation and a bare particle ending. That maximises gate recall and terminates before anchor generation, saving scoring tokens, at the cost of an unmeasured false-positive rate and of letting a string test make a linguistic judgment.

### Decision

The gate proposes only what a string test can prove. Everything else it measures and hands on, and the Reviewer decides.

- `EMPTY_OUTPUT`, `OVER_SENTENCE_LIMIT`, and `VERBATIM_SOURCE_COPY` stay gate decisions: a zero length, a sentence count above three, and full containment at coverage near 1.0 are cases where the measurement is itself the conclusion.
- `OBVIOUS_TRUNCATION` is now a review decision. The gate proposes it only on a trailing comma or colon or an unclosed delimiter, which stayed at 3 of 3 confirmed in this run and costs nothing to keep. A missing sentence-final character, a bare noun ending, a particle ending, or a clause without a predicate are reported as evidence and left to the Reviewer, which is already reading the article and the candidate.
- The Reviewer's soft-score pass may escalate `OBVIOUS_TRUNCATION` on its own reading, whatever the gate decided.

Rationale: every other stage in this design already separates provable measurement from semantic judgment. Truncation was the one place where a regular expression was asked to decide whether a sentence had finished. Moving it costs nothing, because the Reviewer reads the text anyway, and it protects the gate's demonstrated precision. The accepted cost is that a truncated candidate now consumes anchor generation and scoring before terminating: 14 of 250 in this run, roughly 6 percent of scoring work.

### What the gate provides

The gate is a measurement instrument. Its truncation evidence now carries `sentence_count`, `character_count`, `unclosed_delimiters`, `final_character`, `missing_terminal_punctuation`, `hard_truncation`, and `suspected_truncation`. The Claude gate previously computed neither `missing_terminal_punctuation` nor `character_count`, so the Reviewer could not see the strongest available signal; both are now emitted as evidence only.

### Changes

Both plugins, now identical in behaviour:

- `scripts/hard_gate.py`: proposes truncation on `hard_truncation` only. The GPT gate previously proposed on `suspected_truncation`; the Claude gate gained the two missing evidence fields.
- the Reviewer contract and `references/agent-prompts.md`: the soft-score pass may escalate `OBVIOUS_TRUNCATION`, with the criteria stated.
- `references/rubric.md`: item 4 rewritten to say truncation is a review decision rather than a gate decision.
- `SKILL.md` step 11: `OBVIOUS_TRUNCATION` added to the escalations reachable at the soft-score stage.
- `references/rubric.md` and the Reviewer contract also now state that the article record is its title plus its body and that both count as source. This gap caused a real error in the Claude run: the grounding-review batches were built without the title, so the Reviewer audited the gate with less evidence than the gate had and rejected a valid `FACTUAL_REVERSAL` proposal as unreproducible. The Scorer's backstop re-raised it and the soft-score Reviewer confirmed it once the title was present.

Verification on the 250-pair input: the gate still proposes exactly 53 terminals, 50 copies and 3 truncations, so behaviour is unchanged where it should be. The new evidence field flags 17 candidates as lacking sentence-final punctuation, and the corpus contains 17 planted truncated-reference candidates; the counts match, though they have not been compared as sets.

Not yet done: no run has exercised the new escalation path. The next run, which will also have the embedding stage enabled, is the one that tests it.

## 2026-08-20 — Some Truncations Are Undecidable Without a Reference

A one-record smoke test after the truncation fix contradicted the expectation behind the fix, which makes it the most useful result of the day.

Test candidate `51395937_e409196f`, a leading fragment of its article's reference summary cut so that `方針を発表した。` became `方針を発表`. All four stages ran, with the embedding gate live for the first time: the physical gate flagged without proposing (`final_character` `表`, `missing_terminal_punctuation` true, `hard_truncation` false); the embedding gate reached the local model and returned `assigned_similarity` 0.7494 in `assigned_article_only` mode with zero cross-article comparisons; the Grounding Gate returned `GROUNDED`, citing the new peripheral-defect counter-example; the Scorer scored 60 MIXED and recorded the broken ending in `issues` without proposing a terminal.

The Reviewer then reached the restored escalation path, compared the candidate against the `TRUNCATED` few-shot, and declined to escalate. Its argument: `…方針を発表` is ordinary Japanese news 体言止め, where the verbal noun discharges the main clause while every argument is present, so absent sentence-final punctuation is a register choice rather than a stop mid-thought. It also revised the score upward, 60 MIXED to 69 FINE, on the ground that coherence 6 of 15 belongs to genuinely garbled text.

The corpus shows the candidate was cut mid-predicate: the characters after the cut are `した。`. So the verdict is wrong about the fact and correct about the evidence. `〜を発表` is simultaneously a legitimate headline register and the residue of cutting `〜を発表した。`, and the deleted text is the only thing that separates them. A reference-free evaluator does not have it. No prompt, rule, or agent working from the article and the candidate alone can decide this case.

This splits the 14 truncations the full run missed into two groups that must never again be reported as one:

- **amputated mid-token**, endings such as `しかしそ`, `女性2人が車`, `このうち4割`, `救助し`. The break is visible in the text, so a Reviewer can be expected to catch these, and missing them is a recall problem worth measuring.
- **体言止め endings**, such as `発表` and `入植地`. Undecidable from the pair alone. Missing them is a limit of the reference-free contract, not a defect in the funnel, and must not be counted against the evaluator.

So the earlier framing was wrong twice over: restoring the Reviewer's escalation permission was necessary but does not recover the whole class, and part of the class is unrecoverable by construction. The escalation path itself is confirmed working, having been reached, exercised, and used to reach a reasoned negative. The permission was the fix; the judgment stays with the Reviewer.

One further finding from the same test: the Reviewer noticed the draft's trace jumped from `embedding_relevance` to `draft_scoring` with no `grounding_gate` entry, so `eligible_for_soft_scoring: true` was not reproducible from the trace. The cause was orchestration, the gate and Scorer having been launched in parallel to save a round trip, so the Scorer's input never carried the gate's trace event. Absent from a sequential run, but it shows a missing stage is visible from the artifact alone.

Still untested: whether a Reviewer catches the amputated-mid-token group. This test covered only the undecidable group.

## Language Policy

Project-facing documentation, prompts, labels, reports, charts, and code messages are English. Japanese source articles, candidate summaries, evidence spans, and language-specific fixtures remain Japanese because translating them would change the evaluation task.

## Next Validation Work

- Run article-level held-out evaluation.
- Add controlled perturbations for numbers, entities, negation, causality, and truncation.
- Measure within-article ranking agreement against human labels.
- Measure precision and recall for each terminal failure mode.
- Recalibrate the embedding relevance gate across models and domains.
- Treat autonomous web corpus expansion as a separate, explicitly authorized project with provenance and licensing controls.
