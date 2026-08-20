# Summary quality rubric

## Contract

Evaluate only the input article and candidate summary. The article record is its title plus its body, and both count as source. Do not require a dataset reference summary. Return a score, label, evidence, review status, and trace.

## Eligibility and terminal results

Hard constraints come in two layers and a candidate must clear both before it is scored.

**Layer 1, physical.** Deterministic string and structure tests that a script can prove: items 1 to 4 below.

**Layer 2, semantic.** The Grounding Gate Agent, items 5 to 7 below. No string test and no embedding can prove these, so a dedicated agent judges one question only: is this candidate grounded in the supplied article at all? It never scores quality. This is the last line of defence before scoring, and every proposal it makes is confirmed or rejected by the independent Reviewer.

1. `EMPTY_OUTPUT`: normalized candidate is empty.
2. `OVER_SENTENCE_LIMIT`: candidate contains more than three top-level sentences.
3. `VERBATIM_SOURCE_COPY`: whole or almost whole candidate is a continuous/high-coverage copy of the input body. Ordinary entity, number, quotation, and short-phrase overlap is insufficient.
4. `OBVIOUS_TRUNCATION`: the candidate is a fragment that no longer carries the article's content. Truncation is a review decision, and the bar for terminating is high.

   The deterministic gate proposes this only on evidence a string test can prove, a final comma or colon or an unclosed bracket or quotation. Everything else it records and passes on, including a candidate ending without sentence-final punctuation, on a bare noun, or on a clause with no predicate.

   The Reviewer then decides on this rule: **a cut candidate that still reports what the article is about is not terminal.** It stays in soft scoring and loses coherence in proportion to how broken the reading is, with faithfulness and coverage judged on what it actually says. Terminate only when the fragment carries no usable content at all, for example a stub that names a subject and stops before saying anything about it.

   This deliberately declines to distinguish a deliberate headline register from a cut, because the two are not separable from the article and the candidate alone. Both are penalized as reading defects rather than routed to `0`.
5. `OFF_TOPIC`: candidate is unrelated to its assigned article. Judge this from the article and the candidate alone; embedding similarity may nominate and independent review must confirm. Confirmed `OFF_TOPIC` receives score `0` and ranks last without dispute.
6. `FACTUAL_REVERSAL`: candidate asserts the opposite of the article's main event or its central outcome. The wording is fluent and the topic is correct, so nothing upstream can see it.
7. `FABRICATED_CONTENT`: the candidate's central content has no basis in the article at all. The event, outcome, decision, quotation, or figure that carries the summary's message appears nowhere in the source.

Items 5 to 7 are terminal only when the defect is central. Judge centrality against the anchor's `main_event`:

- `FACTUAL_REVERSAL` covers a negated main event, an inverted outcome, an inverted state or condition, or an inverted decision.
- `FABRICATED_CONTENT` covers an invented main event, an invented outcome, an invented attributed quotation, or an invented figure that the summary's message rests on.
- A wrong peripheral number, a wrong secondary entity, one added unsupported detail, or a reversed or invented minor sub-claim stays inside soft scoring as a faithfulness penalty.

When the central fact survives and only details are wrong, the gate returns `GROUNDED` and scoring continues. This boundary is what keeps the soft gradient alive: without it every wrong figure would collapse to `0`.

Keep failure category separate from soft quality. Copy and truncation do not enter soft scoring, but they rank above confirmed off-topic content. Use `terminal_rank` rather than inventing fake soft dimension scores:

| Terminal result | score | terminal_rank |
|---|---:|---:|
| `FACTUAL_REVERSAL` | 0 | 0 |
| `FABRICATED_CONTENT` | 0 | 0 |
| `OFF_TOPIC` | 0 | 0 |
| `EMPTY_OUTPUT` | 0 | 0 |
| `VERBATIM_SOURCE_COPY` | 0 | 1 |
| `OBVIOUS_TRUNCATION` | 0 | 2 |
| `OVER_SENTENCE_LIMIT` | 0 | 3 |

`FACTUAL_REVERSAL` and `FABRICATED_CONTENT` share the worst tier with off-topic and empty output. A summary that states the opposite of the article misleads a reader who cannot check the source, so it is at least as harmful as one that is merely irrelevant, and it must never outrank a truncated or copied candidate.

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
- `FINE` (`65–74`, sound but with one clear weakness)
- `MIXED` (`50–64`)
- `POOR` (`0–49`, eligible but low quality)

`FINE` splits the old `50–74` band. The upper half held candidates that are usable with one visible gap, such as a missing secondary fact or a minor unsupported detail, while the lower half held candidates a reader should not rely on. Collapsing both into `MIXED` hid that difference. The `GOOD`, `EXCELLENT`, and `POOR` boundaries are unchanged.

## Review policy

- Approve a terminal result only when evidence is sufficient and reproducible.
- Reject an uncertain hard gate and continue the funnel.
- Verify every factual claim against the article, every score against the rubric, and all arithmetic.
- Never average Scorer and Reviewer numbers. Return explicit corrections, revise once, and preserve unresolved disagreement as `LOW_CONFIDENCE`.
