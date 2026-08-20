# Evaluating a Japanese News Summarizer

A reference-free quality funnel, built twice and checked against itself.

---

## 1. Exploration

The corpus is 250 candidate summaries over 50 BBC Japanese articles, five per article, methods undisclosed. I read all 250 against their sources rather than sampling, because the interesting failures turned out to be invisible in aggregate statistics.

**What the surface tells you, and where it stops.** Three patterns fall out of exact string comparison alone: 51 candidates reproduce the article's own opening block verbatim — caption line, byline and all, one even carrying a typo from the source; 17 are reference summaries cut mid-sentence; 16 are another article's reference summary filed under the wrong article. That is 84 of 250 decided by string tests and one similarity check, with no model judgment involved.

The remaining 166 are where the problem actually lives. Reading them surfaced a class the surface cannot touch: candidates that are fluent, correctly sized, on topic, not copied — and wrong. `52000333_4f9df41b` reports that a nationwide closure was called off; the article announces it. `44708203_437c2afb` describes rescued boys as gravely weakened; the article shows them smiling and introducing themselves. `50469832_8a6e1840` states the real policy shift correctly, then attaches an emergency UN Security Council session and a unanimous condemnation resolution that exist nowhere in the source.

**Two hypotheses died here.** The first was that embedding similarity could grade quality. It cannot, and the direction of the error matters: a verbatim copy scores *highest* of all, because copying maximises similarity. Similarity is a topic signal, and every dangerous candidate above is on topic. The second was that reference summaries could serve as the comparator. A production request contains an article and a candidate and nothing else; an evaluator that needs a reference has not been evaluated at all. Both hypotheses were abandoned early, and the second reshaped the whole architecture.

**What survived** is a severity distinction that turned out to be the design's hinge. `50469832_8a6e1840` invents a Security Council resolution but states its main event correctly — delete the invented sentence and the summary still stands. `41875333_aa36a21a` replaces a real quotation with an invented one of opposite meaning — nothing correct is left to stand on. Both are fabrication; only one destroys the output. Conspicuousness is not severity. Centrality is.

![Failure modes](figures/failure_modes.drawio) — *open in diagrams.net; PNG equivalents in the same folder*

## 2. Design

Three layers, cheapest first, and nothing terminates without an independent reviewer confirming it.

**Layer 1, physical.** A script proposes only what a string test proves: empty output, more than three sentences, continuous source copying, a trailing comma or unclosed delimiter. It proposes; it never decides.

**Layer 2, semantic.** A dedicated Grounding Gate agent answers one question — is this candidate grounded in its article? — returning `OFF_TOPIC`, `FACTUAL_REVERSAL` or `FABRICATED_CONTENT` with one cited span from each text. It never sees the anchor, the scoring rubric, or another article, and it never produces a score. That isolation is deliberate: an agent that both screens and grades will trade a central defect for a low number instead of stopping it. An embedding check runs before it as a cheap hint, comparing the candidate only with its own assigned article, and is never terminal on its own.

**Layer 3, soft scoring.** Survivors get an article-only anchor (main event, key facts), then atomic claim checks with cited source spans, then four dimensions: faithfulness 50, coverage 30, coherence 15, conciseness 5.

**The centrality boundary** governs which layer owns a defect. A negated main event, an inverted outcome, or an invented core claim is terminal. A wrong secondary entity, a wrong peripheral figure, or one invented claim standing beside a correct central event is a faithfulness penalty. The operational test is deletion: if removing the defective sentence leaves the summary intact, the defect is peripheral.

**Rejected alternatives.** A cross-encoder reranker: it answers relevance, and our question was a coarse relevant/unrelated split that a 0.6B embedding already separated by 0.31 in cosine, so it added a 2GB dependency and no information. BM25: character-level copy ratio covers the same ground deterministically. Anchor embeddings as a scoring feature: measured, mixed, dropped. A flat 25% copy penalty: unsupported by the brief and withdrawn.

![Funnel architecture](figures/funnel_architecture.drawio)

## 3. Validation

I built the design twice — once as a Claude plugin, once as a GPT/Codex plugin — and ran both over all 250 pairs. Neither used a reference summary at runtime; neither saw the other's output. Four independent lines of evidence follow.

**Against weak labels.** Planted categories were derived offline from the corpus after both runs were final. Agreement on the 141 gradable records: **129/141 = 91.5%**. Copies 50/50, off-topic 16/16, reference-grade candidates 58/58 correctly kept alive with mean 78.6.

**Within-article ordering.** Across all 50 articles, **zero inversions** — no planted degradation ever outranked a reference-grade candidate. The 58 reference-verbatim candidates land at rank 1 or 2 in 96.6% of articles; where a generated summary displaced one, it was a genuinely good summary, never a defective one.

**Between the two implementations.** Routing agreed on **90.0%** of pairs (225/250). Where both terminated, they chose the **same category 71/71 = 100%**. On the 154 both scored, Spearman **0.897**, mean absolute difference 7.2 of 100.

The 25 disagreements are the most informative result in this report, because the two sets do not overlap at all. All 14 that only implementation A terminated are reversals or fabrications, and all 14 are `GENERATED` candidates — implementation B has no grounding-gate agent and structurally cannot reach that class. All 11 that only B terminated are truncations, and all 11 are `REF_TRUNCATED` fragments — A treats truncation as a scaled penalty and scored them 39–70 instead of zero. **The implementations never disagree about which candidates are defective, only about severity, and each disagreement maps onto exactly one documented rule choice.**

**Internal reliability.** The corpus contains six byte-identical candidate pairs. Scored independently by different agents, all **6/6 produced identical scores** — an unplanned test-retest check. Separately, 170 draft scores had zero arithmetic errors, and 250 final records passed schema validation.

![Funnel results and cross-validation](figures/funnel_results.drawio)

## 4. Limitations

**109 candidates have no ground truth.** The generated candidates are 43% of the corpus and the weak-label check cannot reach them. The 91.5% figure describes the labelled remainder only.

**Fabrication is adjudicated inconsistently.** All 8 gate-level `FABRICATED_CONTENT` proposals were released at review; the claim-level backstop re-proposed 4 and 1 was confirmed. Reversal and off-topic confirmed at 100%. The category is real but the threshold is unstable, and reviewers flagged these with MEDIUM confidence — honestly, not silently.

**Some truncations are undecidable.** `〜を発表` is both legitimate Japanese headline register and the residue of cutting `〜を発表した。`. Only the deleted text distinguishes them, and a reference-free evaluator does not have it. This is a limit of the contract, not a defect in the funnel.

**Reference reachability is prevented by convention, not construction.** The reviewer's inputs contained no reference field, but the corpus on disk did, and the reviewer held file-read tools. Nothing but the prompt stopped it. A corpus-blind reviewer with no file access is written and committed but unexercised; the next version should re-adjudicate the 85 terminal decisions with it and report the delta. Until that number exists, no claim about production-shaped review is warranted.

**Next, in order:** reconcile the truncation rule with its label definition and re-measure; run the blind reviewer over the terminal set; obtain human rankings for the 109 unlabelled candidates; recalibrate the 0.50 similarity threshold before any change of model, language or domain.

**Verdict: a usable prototype with unusually well-characterised failure modes, not a validated production evaluator.**
