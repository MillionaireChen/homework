# Submission — Japanese News Summary Quality Evaluation

Two independent implementations of one reference-free evaluation design, each run over all 250 pairs, then cross-validated against each other.

**Start with [`report.md`](report.md).** It is the primary artifact.

---

## What is here

```
submission/
├── report.md                  primary artifact: exploration, design, validation, limitations
├── scores.jsonl               250 rows, one per summary_id, both implementations per row
├── cross_validation.json      machine-readable agreement statistics between the two
├── figures/
│   ├── *.png / *.svg         diagrams and charts embedded by the report (script-generated)
│   └── *.drawio              editable source of the three diagrams (diagrams.net)
├── code/
│   ├── implementation_a_claude/   Claude Code plugin: skill, 4 agents, scripts
│   ├── implementation_b_gpt/      GPT/Codex plugin: skill, agents, scripts
│   ├── exploration/               data exploration and embedding calibration
│   └── cross_validation/          compare_implementations.py
└── runs/
    ├── implementation_a_claude_full250/   full audit trail: gates, reviews, drafts, verdicts
    └── implementation_b_gpt_full250/      same, for the second implementation
```

Two further documents in the repository root record how the work actually proceeded, including
abandoned approaches and corrections: `processing.md` (decision log) and `DESIGN.md` (design as it
stood at the end).

## scores.jsonl format

One JSON object per line, one line per `summary_id`, 250 lines.

| Field | Meaning |
|---|---|
| `summary_id`, `article_id` | join keys |
| `score` | **primary score, 0–100.** Implementation A. A terminated candidate scores 0 |
| `quality_label` | `EXCELLENT` 90-100, `GOOD` 75-89, `FINE` 65-74, `MIXED` 50-64, `POOR` 0-49, or the terminal category |
| `terminal_result` | `null`, or `OFF_TOPIC` / `FACTUAL_REVERSAL` / `FABRICATED_CONTENT` / `VERBATIM_SOURCE_COPY` / `OBVIOUS_TRUNCATION` |
| `terminal_rank` | severity tier for terminated candidates: 0 worst → 3 least severe |
| `dimensions` | `faithfulness` /50, `coverage` /30, `coherence` /15, `conciseness` /5; `null` when terminated |
| `rank_within_article` | 1–5 within its article |
| `implementation_a_claude`, `implementation_b_gpt` | each implementation's own verdict |
| `implementations_agree_on_routing` | did both terminate, or both score? |
| `score_delta` | A minus B, where both scored |

`score` is comparable within an article and across articles: the dimensions are absolute and the
anchor is regenerated per article rather than carried between them.

The per-run files under `runs/` carry the full evidence for every row — claim checks with cited
source spans, gate proposals, reviewer verdicts, and a stage-by-stage trace.

## How to run

Both implementations are **plugins**. You install one and give it one instruction; the plugin runs
the whole cascade itself, spawning its own gate, scorer, reviewer and reporter agents. Everything
below is what those agents run internally — you do not drive the stages by hand.

### Implementation A — Claude Code plugin

The repository already ships the install config at `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "local": { "source": { "source": "directory", "path": "./plugin_claude" } }
  },
  "enabledPlugins": { "summary-quality-funnel@local": true }
}
```

Open the repository in Claude Code and the plugin loads. In an interactive terminal session you can
instead run `/plugin marketplace add ./plugin_claude` then `/plugin install summary-quality-funnel@local`.

Then one command:

```
/summary-quality-funnel:evaluate-summaries evaluate all 250 pairs in data/
```

That is the whole reproduction step. The command runs the physical gates, the embedding hint, the
grounding gate, per-article anchors, scoring and independent review, then validates, ranks, charts
and reports. It provides four agents — `summary-grounding-gate`, `summary-scorer`,
`summary-reviewer`, `summary-reporter` — plus a fifth, `summary-reviewer-blind`, which is committed
but deliberately not used in this run (see Limitations).

### Implementation B — Codex plugin

Manifest at `plugin_GPT/summary-quality-funnel/.codex-plugin/plugin.json`, installed the way Codex
installs a local plugin. Once installed it appears in the command list as two entries you invoke
directly:

- **Summary Quality Funnel** — hard gates, reviewed scoring, report agent, and audit trails
- **Summary Report Agent** — run fixed report code and author only the conclusion

Pick the funnel entry and give it the batch:

```
Evaluate and rank all 250 article-summary pairs in data/, then generate the chart report.
```

Same shape as implementation A: one invocation, and the plugin spawns its own Scorer, Reviewer and
Report subagents for the whole cascade.

### Environment the agents rely on

```bash
python3 -m venv .venv && .venv/bin/pip install numpy requests matplotlib
ollama pull qwen3-embedding:0.6b     # optional
```

The embedding stage only produces a hint and is never terminal, so a run without Ollama still
completes — implementation B's own full-250 run was executed with the embedding stage unavailable.

### Inspecting or re-deriving results without re-running

The deterministic parts of each plugin are plain scripts and can be replayed against the committed
run artifacts:

```bash
S=submission/code/implementation_a_claude/summary-quality-funnel/skills/evaluate-summary-quality/scripts
.venv/bin/python $S/validate_result.py    runs/implementation_a_claude_full250/score.jsonl
.venv/bin/python $S/rank_results.py       --input  runs/implementation_a_claude_full250/score.jsonl \
                                          --output /tmp/ranked.jsonl
.venv/bin/python $S/make_report_charts.py --input /tmp/ranked.jsonl --outdir /tmp/figs
```

Cross-validating the two implementations is a single script and needs no agents:

```bash
.venv/bin/python submission/code/cross_validation/compare_implementations.py \
  --claude runs/implementation_a_claude_full250/score_ranked.jsonl \
  --gpt    runs/implementation_b_gpt_full250/score.jsonl \
  --articles ../data/articles.jsonl --summaries ../data/summaries.jsonl \
  --outdir cross_validation/
```

**Reference summaries never enter the runtime path.** `hard_gate.py` strips the field, and
`validate_result.py` rejects any output containing it. They are read in exactly two offline places,
both after scoring was final: the weak-label check and this cross-validation.

## How AI tools were used

The assistant did the implementation, the runs, and the drafting. **The architecture is mine**, and
so is the record of what I tried and discarded on the way to it.

### The design decisions were mine

- **The cascade itself.** I proposed the funnel: cheap deterministic checks first, embeddings second,
  model judgment last, each stage handling only what the previous one left. The reasons were mine
  too — cost, latency, and that a deterministic rejection is explainable while a probabilistic one
  is not. Early exit is a direct consequence: 80 of 250 pairs never reached the two most expensive
  stages.
- **Hard versus soft constraints.** My framing. A violation of a hard constraint settles the verdict;
  soft constraints only grade what survives. The two-tier output — terminal categories with rank
  tiers, plus a 0–100 score — follows from it.
- **Reference summaries must not enter the evaluation path.** The assistant's first design used them
  as a coverage comparator and ranking anchor. I rejected it: a production request has no reference.
  This turned a reference-based ensemble into the reference-free funnel and is the single most
  consequential decision here.
- **Copy detection belongs to string matching, not embeddings** — embeddings score a verbatim copy
  highest of all, so using them there rewards the failure.
- **Build it twice and cross-validate.** Mine, and it produced the strongest evidence in this
  submission.
- **Reference reachability.** After the full run I noticed the reviewer could still have opened the
  corpus file containing reference summaries: the guarantee was a convention, not a property. I asked
  for a corpus-blind reviewer and then deliberately deferred exercising it, with a defined
  measurement attached, rather than let development run on.
- **Scope and stopping.** Which experiments to run, when a result was good enough, when to stop.

### Approaches I proposed and then did not adopt

Recorded because the rejections shaped the design as much as the acceptances. All are in
`processing.md` with the reasoning at the time.

- **A weighted ensemble of four evaluators** — human 0.4, expert agent 0.2, claim-level check 0.2,
  rule layer 0.2. Dropped: a score containing a human term cannot run on new data, and treating the
  rule layer as a 0.1 voter throws away the one thing it is good for, which is deciding.
- **Full human annotation of all 250 pairs**, split into dev and held-out halves, to distil expert
  rules and then transplant them into a judge prompt. Dropped on cost once the deterministic layers
  turned out to settle 84 pairs on their own, and because a human term in the score defeats the
  reference-free goal in the same way a reference does.
- **Using the reference answers as ground truth to build a golden set cheaply.** Attractive, and
  explicitly warned against by the brief. Kept only as an offline weak-label check after scoring was
  final.
- **A cross-encoder reranker (BGE).** I asked for it to be tried. It was, on all 250: it agreed with
  the embedding gate 16/16 on the off-topic set and added nothing, at a 2GB model and much slower
  inference. Kept as cross-validation evidence, dropped from the pipeline.
- **Embedding the candidate against the generated anchor** as a scoring feature. Measured, mixed
  result, dropped.

### AI-assisted

Implementing the scripts and agent prompts; executing the 250-pair runs; translating the corpus so I
could read it; computing statistics and drawing figures; drafting this README and the report from
results I had reviewed.

### Interactions that materially shaped the result

The reference-summary correction, and a follow-on error where the assistant misdescribed
`reference_summary` as a "summary-like passage inside the article" and pulled the discussion into
whether copying it counted as plagiarism — I corrected that and had the mistake written into
`processing.md` rather than quietly fixed. The hard/soft framing. The decision to make truncation a
scaled penalty instead of a terminal, which is the origin of the single documented divergence
between the two implementations. And the reference-reachability observation, recorded as an open
limitation rather than presented as solved.

## Honest summary of what this establishes

91.5% agreement with weak labels on 141 gradable records, zero within-article ordering inversions
across 50 articles, 90.0% routing agreement and 0.897 score correlation between two independent
implementations, and 6/6 identical scores on byte-identical candidate pairs.

It does not establish production readiness: one corpus, one language, no human ranking comparison,
43% of the corpus unlabelled, and a reference-free guarantee that rests on convention rather than
construction. The limitations section of the report states each of these with the measurement that
would close it.
