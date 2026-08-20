# Summary Quality Evaluation Report

## 1. Input Data

The validated input file `score_ranked.jsonl` contains 250 Japanese news article-summary pairs from 50 unique articles. Runtime scoring did not use reference summaries.

## 2. Funnel Outcomes

173 pairs completed soft scoring and 77 stopped early. Terminal outcomes were 7 factual reversal, 50 verbatim source copy, 3 obvious truncation, 17 off-topic. The deterministic gate proposed 53 terminal outcomes, and downstream review recovered 0 additional hard failures. Embedding evidence nominated 19 off-topic suspects; the Reviewer confirmed 17 and rejected 2. Embedding evidence alone was not terminal.

![Pipeline outcomes](report_assets/pipeline_outcomes.png)

## 3. Results

The 173 soft scores had a mean of 76.15, a median of 82, and a range of 28–100. The label distribution was 52 EXCELLENT, 49 GOOD, 26 FINE, 26 MIXED, 20 POOR. Mean dimension scores were 37.44/50 for faithfulness, 20.02/30 for coverage, 13.88/15 for coherence, and 4.81/5 for conciseness.

The Reviewer approved 250 of 250 final records. 95 were approved without revision, 155 required at least one revision, and 0 remained escalated. The highest soft score was 100 for `54083932_011d6de7`; the lowest was 28 for `44026917_0884546b`.

![Reviewer-approved soft scores](report_assets/soft_score_results.png)

## 4. Conclusion

This full250 run supports an internally consistent, review-complete prototype across 250 pairs, with 173 records receiving soft scores and 77 routed to terminal outcomes. Verbatim-source copying was the dominant terminal outcome (50 cases), while 155 records were revised at least once before approval. Runtime reference summaries were withheld, so these results describe pipeline behavior and internal audit completion, not objective accuracy. The observed scores and approvals therefore do not establish generalization, production readiness, or correlation with human judgments; external item-level labels and held-out, broader-domain validation remain necessary.
