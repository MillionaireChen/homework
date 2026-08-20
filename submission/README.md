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
│   ├── *.drawio               editable diagrams (diagrams.net / VS Code Draw.io extension)
│   └── *.png                  generated charts (deterministic, produced by script)
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

AI assistance was heavy on execution and analysis. The judgment calls that shaped the design were
mine, and several of them were corrections of the assistant's direction.

**My decisions, including corrections I had to make:**

- **Reference summaries must not enter the evaluation path.** The assistant's first design used them
  as a coverage comparator and ranking anchor. I rejected it: a production request has no reference.
  This changed the architecture from a reference-based ensemble into a reference-free funnel, and it
  is the single most consequential decision in the project.
- **The assistant then misframed the field itself**, describing `reference_summary` as a
  "summary-like passage inside the article" and dragging the discussion into whether copying it
  counted as plagiarism. It is the reference answer. I corrected this and had the error recorded in
  `processing.md` rather than quietly fixed.
- **Hard versus soft constraints, and cheap-before-expensive ordering.** Mine. String tests first,
  embeddings second, model judgment last, each stage only handling what the previous one left — for
  cost, latency, and because a deterministic rejection is explainable and a probabilistic one is not.
- **Copy detection belongs to string matching, not embeddings** — embeddings score a verbatim copy
  highest of all.
- **Reference reachability.** After the full run I observed that the reviewer, the last line of
  defence, could still have opened the corpus file containing reference summaries. The guarantee was
  a convention, not a property. I asked for a corpus-blind reviewer and, rather than let the work run
  on indefinitely, deferred exercising it to the next version with a defined measurement attached.
- **Scope and stopping.** Which experiments to run, when a result was good enough, and when to stop.
- Direction to build the design twice and cross-validate, which produced the strongest evidence here.

**AI-assisted:** implementing the scripts and agent prompts; running the 250-pair evaluations;
translating the corpus for my own reading; computing statistics and drawing charts; drafting this
report and README from results I had reviewed.

**Interactions that materially shaped the result:** the reference-summary correction and its
follow-on misframing; the hard/soft constraint framing; the decision to keep truncation as a scaled
penalty rather than a terminal, which is the origin of the single documented divergence between the
two implementations; and the reference-reachability observation, recorded as an open limitation
rather than presented as solved.

## Honest summary of what this establishes

91.5% agreement with weak labels on 141 gradable records, zero within-article ordering inversions
across 50 articles, 90.0% routing agreement and 0.897 score correlation between two independent
implementations, and 6/6 identical scores on byte-identical candidate pairs.

It does not establish production readiness: one corpus, one language, no human ranking comparison,
43% of the corpus unlabelled, and a reference-free guarantee that rests on convention rather than
construction. The limitations section of the report states each of these with the measurement that
would close it.
