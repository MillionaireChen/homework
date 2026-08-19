# Summary quality rubric

## Contract

Evaluate only the input article and candidate summary. Do not require a dataset reference summary. Return a score, label, evidence, review status, and trace.

## Eligibility and terminal results

Only candidates that pass every hard gate qualify for soft scoring. Hard failures receive deterministic terminal results after Reviewer confirmation.

1. `EMPTY_OUTPUT`: normalized candidate is empty.
2. `OVER_SENTENCE_LIMIT`: candidate contains more than three top-level sentences.
3. `VERBATIM_SOURCE_COPY`: whole or almost whole candidate is a continuous/high-coverage copy of the input body. Ordinary entity, number, quotation, and short-phrase overlap is insufficient.
4. `OBVIOUS_TRUNCATION`: high-confidence physical truncation such as a final comma/colon or unclosed bracket/quote. Treat particle endings as suspicion, not automatic failure.
5. `OFF_TOPIC`: candidate is unrelated to its assigned article. Embedding may nominate; independent review must confirm. Confirmed `OFF_TOPIC` receives score `0` and ranks last without dispute.

Keep failure category separate from soft quality. Copy and truncation do not enter soft scoring, but they rank above confirmed off-topic content. Use `terminal_rank` rather than inventing fake soft dimension scores:

| Terminal result | score | terminal_rank |
|---|---:|---:|
| `OFF_TOPIC` | 0 | 0 |
| `VERBATIM_SOURCE_COPY` | 0 | 1 |
| `OBVIOUS_TRUNCATION` | 0 | 2 |
| `OVER_SENTENCE_LIMIT` | 0 | 3 |

Sort first by eligibility, then `terminal_rank` for ineligible items, then soft score for eligible items. This preserves “off-topic is worst” while keeping invalid outputs out of soft scoring.

## Soft score for eligible candidates

| Dimension | Maximum | Evidence standard |
|---|---:|---|
| Faithfulness | 50 | Mark every claim supported, contradicted, or absent in the source. Check entities, numbers, dates, negation, causality, and attribution. |
| Coverage | 30 | Capture the main event, result, and essential key facts. Use the generated anchor as a coverage aid, never as factual ground truth. |
| Coherence | 15 | Be complete, readable, logically ordered, and grammatically coherent. |
| Conciseness | 5 | Stay focused and avoid unnecessary detail or repetition. |

`score = faithfulness + coverage + coherence + conciseness`.

## Generated anchor

Generate the anchor from the article before showing any candidate:

```json
{
  "main_event": "...",
  "key_facts": ["..."],
  "anchor_summary": "Two or three sentences"
}
```

Use direct source evidence for faithfulness. Use `main_event` and `key_facts` for consistent coverage comparisons. A candidate may contain valid source-supported information absent from the anchor.

## Soft labels

- `EXCELLENT` (`90–100`)
- `GOOD` (`75–89`)
- `MIXED` (`50–74`)
- `POOR` (`0–49`, eligible but low quality)

## Review policy

- Approve a terminal result only when evidence is sufficient and reproducible.
- Reject an uncertain hard gate and continue the funnel.
- Verify every factual claim against the article, every score against the rubric, and all arithmetic.
- Never average Scorer and Reviewer numbers. Return explicit corrections, revise once, and preserve unresolved disagreement as `LOW_CONFIDENCE`.
