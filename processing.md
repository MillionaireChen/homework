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

## 2026-08-20 — Claude Plugin Installed and Brought Level with the GPT Design

The user installed the Claude-side plugin and required it to carry the same design, so the two implementations stay comparable instead of drifting into different rule sets.

### Installation

Claude Code installs plugins through a marketplace, so `plugin_claude/.claude-plugin/marketplace.json` now declares this repository's plugin as marketplace `local`, owner and author Chen Jinhua, with `source: "./summary-quality-funnel"`:

```bash
claude plugin marketplace add "<repo>/plugin_claude"
claude plugin install summary-quality-funnel@local
```

The marketplace points at the working tree rather than a copy, so editing a file in the repository changes the installed plugin with no sync step and no second source of truth.

### Ported from the GPT implementation

Six changes, all previously GPT-only:

1. the Grounding Gate as a fourth agent, `agents/summary-grounding-gate.md`;
2. terminal `FACTUAL_REVERSAL`;
3. terminal `FABRICATED_CONTENT`;
4. soft label `FINE` at 65-74;
5. the embedding gate restricted to the candidate's own assigned article;
6. the Report Agent as the only role permitted to read `reference_summary`, with `scripts/reference_validation.py` for the offline cross-check.

The shared reference files and the two shared scripts were identical to their pre-change GPT counterparts, so they were copied across with line endings normalised, then adapted where the two runtimes genuinely differ:

- `references/agent-prompts.md` addresses this plugin's four named subagents instead of Codex roles;
- `references/output-schema.md` lists this side's chart set (`funnel.png`, `scores_by_article.png`, `categories.png`) rather than the GPT report skill's two charts;
- `scripts/make_report_charts.py` has its own colour tables, so `FINE` and both new terminals were added there by hand;
- reporting stays a single skill with the `summary-reporter` agent, so the cross-check became a report section in that agent's contract instead of a separate report skill.

The three existing agent definitions were updated rather than replaced: the Scorer gained the semantic-terminal backstop, the Reviewer gained a grounding pass and the five-band label check, and the Reporter gained the reference-summary policy and the cross-check section.

Manifest moved to `0.2.0`.

### Verification

- `claude plugin validate` passes for both the plugin manifest and the marketplace manifest.
- Every script parses.
- The rewritten embedding gate passes the same offline fake-vector test used on the GPT side: same-topic pairs score high, an unrelated candidate is nominated, and none of the four prohibited evidence fields appears.
- `scripts/validate_result.py` accepts a well-formed `FACTUAL_REVERSAL` record and rejects the same record with `terminal_rank: 2`.
- The ported `scripts/reference_validation.py` reproduces the GPT result exactly on the 250-pair run: 140 of 141 gradable records, 58 / 50 / 17 / 16 / 109 per category.
- `claude plugin details` reports 4 agents and 2 skills at version 0.2.0, always-on cost ~748 tokens.

`claude plugin update` reports "not found" because the plugin has no git remote to pull from; a local-source install reads the working tree directly, which the version and agent count in `plugin details` confirm.

### Logging convention

Per the user: `processing.md` is the Claude-side log as well as the project decision log, and `progressing_GT.md` stays the GPT/Codex log. A separate `progressing_claude.md` was proposed and then dropped before creation, so no such file exists.

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

## Current Status

The current design has three isolated roles—Scorer, Reviewer, and Report Agent—and a deterministic-to-semantic cascade with early stopping. The next work is broader held-out validation, controlled factual perturbations, human ranking comparison, and threshold recalibration across models and domains.

All project-facing material is English. Japanese source articles, candidate summaries, evidence spans, and language-specific fixtures remain Japanese because they are the evaluated data rather than documentation.
