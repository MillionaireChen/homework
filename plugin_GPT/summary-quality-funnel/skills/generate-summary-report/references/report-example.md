# Report example

Use this synthetic example as the single few-shot example for a Report Agent call.

Audited statistics:

```json
{"input":{"pairs":10,"unique_articles":5,"reference_summary_used":false},"funnel":{"fully_soft_scored":7,"terminal_total":3,"terminal_by_type":{"VERBATIM_SOURCE_COPY":2,"OFF_TOPIC":1}},"soft_scores":{"mean":81.4,"minimum":62,"maximum":97,"labels":{"EXCELLENT":2,"GOOD":3,"MIXED":2}},"review":{"approved":10,"revised_at_least_once":1}}
```

Expected report:

```markdown
## 1. Input Data

The run evaluated 10 article-summary pairs from five articles. Runtime scoring did not use reference summaries.

## 2. Funnel Outcomes

Seven pairs completed soft scoring. Three stopped early: two verbatim source copies and one confirmed off-topic summary.

![Pipeline outcomes](report_assets/pipeline_outcomes.png)

## 3. Results

Soft scores averaged 81.4 and ranged from 62 to 97: two EXCELLENT, three GOOD, and two MIXED. The Reviewer checked all 10 records and required one revision.

![Soft-score results](report_assets/soft_score_results.png)

## 4. Conclusion

This run supports a usable prototype that needs broader validation. The funnel intercepted clear failures and produced auditable scores, but the sample is too small to establish production stability.
```
