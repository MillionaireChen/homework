# Embedding relevance calibration

Read this reference only when selecting or validating an embedding relevance threshold.

## Experiment 1: planted unrelated summaries

Using `qwen3-embedding:0.6b` on 10 articles:

- Relevant-answer group: `0.711–0.868`, mean `0.800`.
- Known unrelated group: `0.163–0.398`, mean `0.275`.
- Observed gap: `0.313`.

## Experiment 2: random held-out articles and random foreign summaries

Using seed `42`, select 10 articles not used in Experiment 1. Pair each with its relevant answer and a randomly selected summary from another article:

- Relevant-answer group: `0.707–0.858`, mean `0.780`.
- Random unrelated group: `0.164–0.364`, mean `0.263`.
- Observed gap: `0.343`.

The second experiment is not restricted to the dataset's planted off-topic cases. It reproduces the first experiment with a disjoint article sample and reproducible random negative pairing.

## Combined interpretation

Across the two experiments (20 relevant and 20 unrelated pairs):

- Relevant range: `0.707–0.868`; weighted mean `0.790`.
- Unrelated range: `0.163–0.398`; weighted mean `0.269`.
- Combined observed separation: `0.309`.
- Threshold `0.5` separates all 40 experimental pairs.

Use `0.5` as the plugin's default engineering threshold for **off-topic nomination** with this model and preprocessing (`title + first 1500 body characters`). Do not turn the embedding signal alone into terminal score `0`.

One known weak article/relevant-answer pair outside these experiments scores `0.459`. Therefore a related item can fall below `0.5`. Route every item below the threshold to the independent Reviewer. Assign terminal `OFF_TOPIC`, score `0`, and last place only after Reviewer confirmation.

In multi-article batches, also use assigned-article rank and margin to the strongest other article. Recalibrate after changing the embedding model, language, domain, article representation, or preprocessing.
