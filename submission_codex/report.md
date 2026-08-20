# Summary Quality Evaluation — Codex Submission

## 1. Exploration

The dataset contains 250 Japanese news-article/candidate pairs: 50 articles and five candidates per article. The evaluation problem is ranking candidates within each article, not finding a universally “good” summary in isolation. Reading the corpus exposed several qualitatively different failures: verbatim copying of the article, summaries about another topic, reversals of the article’s central event, fabricated central claims, unusable fragments, and summaries that remain on-topic but contain wrong entities, numbers, or incomplete coverage.

This led to a funnel rather than a single similarity score. A copied article can have excellent lexical or embedding similarity while failing the task. Conversely, a concise paraphrase can have low surface overlap while being faithful. Therefore string evidence is used first for only provable failures; semantic scoring is reserved for candidates that survive those constraints.

## 2. Evaluation design

The runtime receives only an article and its candidate summary. Reference summaries are withheld. The article title and body are the source of truth.

The pipeline is:

1. **Physical hard gate.** Deterministic checks identify empty input, verbatim source copying, and clearly unusable truncation. These routes stop before expensive model calls.
2. **Assigned-article embedding hint.** A local embedding model compares the candidate only with its own article. It is advisory: a low similarity nominates an off-topic suspect, but never terminates a record by itself.
3. **Grounding Gate Agent.** An independent Codex agent checks whether the candidate is grounded in the supplied article. It can propose `OFF_TOPIC` or `FACTUAL_REVERSAL`; the gate does not assign a score. A separate Reviewer must reproduce the evidence before a terminal decision is accepted.
4. **Soft scoring.** A Scorer creates an article-only anchor and scores four dimensions: faithfulness (50), coverage (30), coherence (15), and conciseness (5). The anchor is a compact coverage aid, not ground truth. Claims receive source evidence and a supported/contradicted/not-in-source status.
5. **Review and revision.** Every score is independently reviewed. A `REVISE` decision permits one bounded Scorer revision followed by final review; unresolved cases would be escalated, but none remained in this run.

The resulting score is comparable across candidates, while the ranking is performed within each article. Terminal outcomes are assigned rank 0 or 1/2 according to severity, so a definite copy or unrelated summary cannot outrank a plausible summary merely because it resembles the source.

The editable design is shown in [`diagrams/pipeline.drawio`](diagrams/pipeline.drawio) and [`diagrams/funnel.drawio`](diagrams/funnel.drawio).

## 3. Validation and results

The full run processed all 250 pairs and produced exactly five records for each of the 50 articles. The final JSONL passed schema validation, dimension arithmetic validation, evidence checks, and ranking-group checks. All 250 records received an independent final Reviewer approval; 155 of the 173 soft-scored records required one revision and none remained escalated.

The funnel outcomes were:

- 173 candidates completed soft scoring;
- 77 terminated early: 50 verbatim source copies, 17 off-topic candidates, 7 central factual reversals, and 3 unusable truncations;
- embedding nominated 19 off-topic suspects; the Reviewer confirmed 17 and rejected 2;
- soft-score mean 76.15, median 82, range 28–100;
- soft labels: 52 EXCELLENT, 49 GOOD, 26 FINE, 26 MIXED, and 20 POOR.

The dimension means among soft-scored candidates were 37.44/50 faithfulness, 20.02/30 coverage, 13.88/15 coherence, and 4.81/5 conciseness. Verbatim copying was the largest terminal class, confirming why lexical similarity cannot be the evaluator’s final objective. The two-stage embedding/reviewer pattern also demonstrates that embeddings are useful as a cost-saving nomination signal, not as an autonomous quality decision.

![Pipeline outcomes](figures/pipeline_outcomes.png)

![Soft-score results](figures/soft_score_results.png)

The experiment establishes that the implementation is operationally complete and produces separated within-article rankings for every article. It does not establish that every rank is objectively correct: there is no human adjudication set, and the evaluator is itself model-assisted.

## 4. Limitations and next steps

The principal limitation is the absence of independent item-level human labels. Reviewer agreement proves that the pipeline is internally audited, not that the judgments match expert readers. The corpus is also one language, one news domain, and only 50 articles; thresholds may shift on other domains, lengths, or writing styles. The embedding stage was run only as assigned-article evidence and was not treated as a calibrated probability. The article-only anchor may omit facts that a human considers important, so coverage remains a judgment rather than a reference-match metric.

Next steps are to blind-label a stratified subset with human annotators, measure pairwise ranking accuracy and calibration, test multilingual and non-news data, and run an ablation comparing the funnel with and without embedding evidence. A held-out threshold set should be used before changing terminal policies or claiming production readiness.

## Conclusion

The Codex implementation is a reproducible, reference-free ranking prototype: it handles hard violations early, reserves semantic effort for survivors, and records evidence and review traces for every decision. On this 250-pair corpus it completed all five-way rankings and achieved full internal review coverage. The results support the pipeline as an engineering scaffold and validation target, not as evidence of human-level correctness or production generalization.
