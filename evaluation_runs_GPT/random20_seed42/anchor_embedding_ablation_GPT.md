# Anchor Embedding Ablation — random20 / seed 42

## Question

Does embedding the candidate summary against an article-generated anchor add useful information beyond embedding it against the full article?

No reference summary was used. Five verbatim-copy cases stopped before embeddings. The embedding comparison therefore contains 15 hard-gate survivors; correlations use the 12 summaries that received Reviewer-approved soft scores.

## Result

| Target | Full article embedding | Anchor embedding | Difference |
|---|---:|---:|---:|
| Coverage Pearson | 0.5046 | 0.5175 | +0.0129 |
| Coverage Spearman | 0.5282 | 0.6303 | +0.1021 |
| Total-score Spearman | -0.0839 | 0.1958 | +0.2797, but still weak |
| Faithfulness Spearman | -0.4099 | -0.0989 | Neither is a faithfulness signal |

The anchor signal follows coverage ordering somewhat better, especially by Spearman correlation. It does not reliably predict factual correctness or the final quality score.

The leave-one-out coverage prediction check does not show a robust gain:

| Features | MAE | RMSE |
|---|---:|---:|
| Full article only | 3.6246 | 4.3461 |
| Anchor only | 4.0123 | 4.3738 |
| Full article + anchor | 4.4121 | 4.8381 |

With only 12 scored observations, adding the anchor feature increases prediction error. It should not yet become a score formula or hard threshold.

## Important counterexample

`40490051_5d9feeef` received only 43 points and faithfulness 8/50 because it reverses the country, attacker gender, age and combatant counts. Its anchor similarity is still 0.7818 because the candidate discusses the same event and concepts. High anchor similarity therefore means semantic overlap, not factual correctness.

The one confirmed off-topic case changed from 0.3193 against the article to 0.2963 against the anchor. This is only a small improvement. Within the 14 sampled anchors it still ranked first for its assigned article, because every anchor was a weak match. Retrieval rank alone is unsafe on a small corpus; absolute similarity and independent review remain necessary.

## Recommended pipeline position

```text
Article + candidate
  -> deterministic hard gates
  -> candidate-to-article embedding relevance gate
  -> Reviewer confirms any OFF_TOPIC proposal
  -> generate article-only anchor
  -> candidate-to-anchor embedding
  -> attach LOW / MID / HIGH coverage signal to Scorer
  -> claim-level faithfulness and coverage scoring
  -> independent Reviewer
```

The new signal should initially be advisory:

- Low anchor similarity: ask the Scorer to inspect missing central facts.
- Medium or high anchor similarity: do not add points automatically.
- Never use anchor similarity to approve faithfulness.
- Never make it a terminal failure without independent semantic confirmation.
- Keep article embedding for off-topic retrieval; use anchor embedding only after relevance passes.

## Decision

Add `anchor_similarity` and its evidence to the scoring trace as an experimental soft coverage feature. Do not change scores automatically yet. Recalibrate on at least 50–100 Reviewer-scored survivors before selecting LOW/MID/HIGH bands or using the feature in a formula.
