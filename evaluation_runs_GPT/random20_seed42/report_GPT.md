# Summary Quality Evaluation Report

## 1. Input Data

The validated input file `score_ranked.jsonl` contains 20 Japanese news article-summary pairs from 14 unique articles. Runtime scoring did not use reference summaries.

## 2. Funnel Outcomes

12 pairs completed soft scoring and 8 stopped early. Terminal outcomes were 5 verbatim source copy, 2 obvious truncation, 1 off-topic. The deterministic gate proposed 5 terminal outcomes, and downstream review recovered 2 additional hard failures. Embedding evidence nominated 1 off-topic suspects; the Reviewer confirmed 1 and rejected 0. Embedding evidence alone was not terminal.

![Pipeline outcomes](report_assets/pipeline_outcomes.png)

## 3. Results

The 12 soft scores had a mean of 76.08, a median of 76, and a range of 43–98. The label distribution was 3 EXCELLENT, 3 GOOD, 5 MIXED, 1 POOR. Mean dimension scores were 35.5/50 for faithfulness, 20.92/30 for coverage, 14.75/15 for coherence, and 4.92/5 for conciseness.

The Reviewer approved 20 of 20 final records. 20 were approved without revision, 0 required at least one revision, and 0 remained escalated. The highest soft score was 98 for `41875333_06c27e30`; the lowest was 43 for `40490051_5d9feeef`.

The optional embedding ablation reported coverage Spearman correlations of 0.5282 for article similarity and 0.6303 for anchor similarity. Leave-one-out coverage MAE was 3.6246 for article similarity, 4.0123 for anchor similarity, and 4.4121 for both features; the lowest error came from article similarity alone. These deterministic results do not establish a stable predictive gain from anchor embeddings.

![Reviewer-approved soft scores](report_assets/soft_score_results.png)

## 4. Conclusion

This run supports a usable prototype that needs broader validation. The funnel handled the observed source-copy, truncation, and off-topic failures and produced internally reviewed soft scores, with three records corrected during review. Reviewer approval confirms audit completion, not objective accuracy. The small 20-pair sample, absence of external item-level gold labels, and mixed anchor-ablation results do not establish production readiness, stability, or generalization. Broader validation should use held-out human judgments across more articles and domains before deployment.
