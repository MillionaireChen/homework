# Submission — Japanese News Summary Quality Evaluation

**The evaluator is a plugin.** One reference-free funnel design, delivered twice — as a Claude Code
plugin and as a Codex plugin — each run over all 250 pairs, then cross-validated against each other.

**Start with [`report.md`](report.md).** It is the primary artifact.

Two different kinds of report live in this zip, and only the first is the deliverable:

- [`report.md`](report.md) — the submission report: exploration, design, validation, limitations. No length or format constraint.
- `runs/*/report.md` — machine-generated *run* reports, written by each plugin's own Report Agent under its product contract: fixed sections, under 800 words, every statistic taken from validated JSON and never computed by the agent. They are evidence about the runs, not the submission report.

---

## Layout

```
submission/
├── report.md                  primary artifact: exploration, design, validation, limitations
├── DESIGN.md                  the design as it stood at the end
├── processing.md              decision log kept while working: hypotheses, corrections, dead ends
├── scores.jsonl               250 rows, one per summary_id, both implementations per row
├── cross_validation.json      machine-readable agreement statistics between the two
├── plugins/                   ← the deliverable
│   ├── a-claude-code/         Claude Code plugin: 1 command, 1 skill, 5 agents, 6 scripts
│   └── b-codex/               Codex plugin: 2 skills, yaml agents, 20 scripts
├── code/
│   ├── exploration/           data exploration, embedding + reranker probes, anchor ablation
│   ├── cross_validation/      compare_implementations.py
│   └── figures/               make_funnel_diagrams.py (drawio) + render_drawio_svg.py (svg)
├── experiments/
│   ├── exploration_outputs/   the probe outputs behind the report's tables
│   ├── plugin_a_claude/       25-pair funnel, anchor ablation, 109-candidate second-opinion audit
│   └── plugin_b_codex/        50-pair funnel experiment
├── figures/
│   ├── *.drawio               editable diagram source — the single source of truth
│   ├── *.svg                  rendered from the .drawio files by render_drawio_svg.py
│   ├── funnel_pipeline.png …  the same SVGs rasterised; the report embeds these, because
│   │                          several markdown viewers refuse to display SVG images
│   └── run_a_*.png xval_*.png charts emitted by the runs themselves
└── runs/
    ├── plugin_a_claude_full250/   full audit trail: gates, reviews, drafts, verdicts, report
    └── plugin_b_codex_full250/    same, for the second plugin
```

Per the assignment's `code/` requirement: the plugins **are** the code that produces `scores.jsonl`.
They live in `plugins/` because they are the deliverable, not a helper. `code/` holds the exploration
and validation scripts that surround them.

## How to run it

Both implementations are plugins. You install one and give it one instruction; the plugin runs the
whole cascade itself, spawning its own gate, scorer, reviewer and reporter agents.

### Environment (required, not optional)

```bash
python3 -m venv .venv && .venv/bin/pip install numpy requests matplotlib
ollama pull qwen3-embedding:0.6b       # required: the relevance band is a mandatory stage
```

The relevance band is **required and never terminal**. A run that cannot reach the embedding model is
an incomplete run, not a cheaper one: every survivor must leave that band carrying a similarity value
in its trace. What the band may never do is decide — it nominates suspects for the next stage.

### Plugin A — Claude Code

Install config is [`plugins/a-claude-code/settings.json.example`](plugins/a-claude-code/settings.json.example);
copy it to `.claude/settings.json` (in the working repository the marketplace path was `./plugin_claude`):

```json
{
  "extraKnownMarketplaces": {
    "local": { "source": { "source": "directory", "path": "./plugins/a-claude-code" } }
  },
  "enabledPlugins": { "summary-quality-funnel@local": true }
}
```

Open the folder in Claude Code and the plugin loads. Interactively you can instead run
`/plugin marketplace add ./plugins/a-claude-code` then `/plugin install summary-quality-funnel@local`.

Then one command:

```
/summary-quality-funnel:evaluate-summaries evaluate all 250 pairs in data/
```

That is the whole reproduction step. It runs the physical gates, the required embedding band, the
grounding gate, per-article anchors, scoring and independent review, then validates, ranks, charts and
reports. The plugin provides four agents — `summary-grounding-gate`, `summary-scorer`,
`summary-reviewer`, `summary-reporter` — plus a fifth, `summary-reviewer-blind`, committed and
deliberately unexercised (see Limitations).

### Plugin B — Codex

Manifest at [`plugins/b-codex/summary-quality-funnel/.codex-plugin/plugin.json`](plugins/b-codex/summary-quality-funnel/.codex-plugin/plugin.json),
installed the way Codex installs a local plugin. It then appears as two directly invocable entries:

- **Summary Quality Funnel** — gates, reviewed scoring, report agent, audit trails
- **Summary Report Agent** — run the fixed report code and author only the conclusion

Pick the funnel entry and give it the batch:

```
Evaluate and rank all 250 article-summary pairs in data/, then generate the chart report.
```

## scores.jsonl

One JSON object per line, one line per `summary_id`, 250 lines.

| Field | Meaning |
|---|---|
| `summary_id`, `article_id` | join keys |
| `score` | **primary score, 0–100** — plugin A. A terminated candidate scores 0 |
| `quality_label` | `EXCELLENT` 90–100, `GOOD` 75–89, `FINE` 65–74, `MIXED` 50–64, `POOR` 0–49, or the terminal category |
| `terminal_result` | `null`, or `OFF_TOPIC` / `FACTUAL_REVERSAL` / `FABRICATED_CONTENT` / `VERBATIM_SOURCE_COPY` / `OBVIOUS_TRUNCATION` |
| `terminal_rank` | severity tier for terminated candidates: 0 worst → 3 least severe |
| `dimensions` | `faithfulness` /50, `coverage` /30, `coherence` /15, `conciseness` /5; `null` when terminated |
| `rank_within_article` | 1–5 within its article |
| `implementation_a_claude`, `implementation_b_gpt` | each plugin's own verdict |
| `implementations_agree_on_routing` | did both terminate, or both score? |
| `score_delta` | A minus B, where both scored |

`score` is comparable within an article and across articles: the dimensions are absolute and the
anchor is regenerated per article rather than carried between them. 85 rows are terminal, 165 scored.

The files under `runs/` carry the full evidence for every row — claim checks with cited source spans,
gate proposals, reviewer verdicts, and a stage-by-stage trace.

## Inspecting results without re-running the agents

The deterministic parts of each plugin are plain scripts and can be replayed against the committed
run artifacts:

```bash
S=plugins/a-claude-code/summary-quality-funnel/skills/evaluate-summary-quality/scripts
python3 $S/validate_result.py    runs/plugin_a_claude_full250/score.jsonl
python3 $S/rank_results.py       --input  runs/plugin_a_claude_full250/score.jsonl \
                                 --output /tmp/ranked.jsonl
python3 $S/make_report_charts.py --input /tmp/ranked.jsonl --outdir /tmp/figs
```

Cross-validating the two plugins is a single script and needs no agents:

```bash
python3 code/cross_validation/compare_implementations.py \
  --claude runs/plugin_a_claude_full250/score_ranked.jsonl \
  --gpt    runs/plugin_b_codex_full250/score.jsonl \
  --articles ../data/articles.jsonl --summaries ../data/summaries.jsonl \
  --outdir /tmp/xval
```

Regenerating the diagrams — draw.io files are the source, the SVGs are rendered from them:

```bash
python3 code/figures/make_funnel_diagrams.py --outdir figures      # writes *.drawio
python3 code/figures/render_drawio_svg.py figures/*.drawio         # writes *.svg
python3 -c "import cairosvg,glob                                   # writes *.png
for f in ['funnel_pipeline','plugin_anatomy','two_plugins']:
    cairosvg.svg2png(url=f'figures/{f}.svg', write_to=f'figures/{f}.png', scale=1.6)"
```

The `.drawio` files are the source of truth: edit one in draw.io, re-run the renderer, and the
figure in the report changes. The report embeds the PNGs only because several markdown viewers
refuse to display SVG images.

**Reference summaries never enter the runtime path.** `hard_gate.py` strips the field and
`validate_result.py` rejects any output containing it. They are read in exactly two offline places,
both after scoring was final: the weak-label check and the cross-validation.

## How AI tools were used

The assistant did the implementation, the runs, and the drafting. **The architecture is mine**, and so
is the record of what I tried and discarded on the way to it.

### The design decisions were mine

- **The funnel itself.** Cheap deterministic checks first, embeddings second, model judgment last,
  each band handling only what the previous one left. The reasons were mine too — cost, latency, and
  that a deterministic rejection is explainable while a probabilistic one is not.
- **Hard versus soft constraints.** A violation of a hard constraint settles the verdict; soft
  constraints only grade what survives. The two-tier output — terminal categories with severity tiers,
  plus a 0–100 score — follows from it.
- **Reference summaries must not enter the evaluation path.** The assistant's first design used them
  as a coverage comparator and ranking anchor. I rejected it: a production request has no reference.
  This turned a reference-based ensemble into the reference-free funnel and is the single most
  consequential decision here.
- **The relevance band is required, and never decisive.** Requiring a stage and trusting a stage are
  separate choices; the embedding band must run and must not terminate.
- **Copy detection belongs to string matching, not embeddings** — embeddings score a verbatim copy
  highest of all, so using them there rewards the failure.
- **Deliver it as a plugin.** So the cascade is installable rather than re-driven by hand, and so role
  isolation is enforced by the host instead of by prompt discipline.
- **Build it twice and cross-validate.** Mine, and it produced the strongest evidence in this
  submission.
- **Reference reachability.** After the full run I noticed the reviewer could still have opened the
  corpus file containing reference summaries: the guarantee was a convention, not a property. I asked
  for a corpus-blind reviewer, then deliberately deferred exercising it with a defined measurement
  attached, rather than let development run on.
- **Scope and stopping.** Which experiments to run, when a result was good enough, when to stop.

### Approaches I proposed and then did not adopt

Recorded because the rejections shaped the design as much as the acceptances. All are in
[`processing.md`](processing.md) with the reasoning at the time.

- **A weighted ensemble of four evaluators** — human 0.4, expert agent 0.2, claim-level check 0.2,
  rule layer 0.2. Dropped: a score containing a human term cannot run on new data, and treating the
  rule layer as a 0.2 voter throws away the one thing it is good for, which is deciding.
- **Full human annotation of all 250 pairs**, split dev/held-out, to distil expert rules into a judge
  prompt. Dropped on cost once the deterministic bands turned out to settle a fifth of the corpus on
  their own, and because a human term defeats the reference-free goal the same way a reference does.
- **Using the reference answers as ground truth** to build a golden set cheaply. Attractive, and
  explicitly warned against by the brief. Kept only as an offline weak-label check after scoring was
  final.
- **A cross-encoder reranker (BGE).** I asked for it to be tried. It was, on all 250: it agreed with
  the embedding band 16/16 on the off-topic set and added nothing, at a 2 GB model and much slower
  inference. Kept as evidence, dropped from the pipeline.
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
scaled penalty instead of a terminal, which is the origin of the single documented divergence between
the two plugins. The correction that the embedding band is required rather than optional. And the
reference-reachability observation, recorded as an open limitation rather than presented as solved.

## What this establishes

Four independent lines of evidence, none of them a single run's self-report:

- **91.5 %** agreement with weak labels on the 141 candidates the corpus can label — copies 50/50, off-topic 16/16, and all 58 reference-grade candidates correctly kept alive.
- **0 of 50** articles placed a planted failure at or above its reference.
- **Spearman 0.956** between two independent judges on the 109 candidates that carry no label at all.
- **90.0 %** routing agreement and **0.897** score correlation between two separately built plugin implementations, with the **identical** terminal category in all 71 cases where both stopped, plus 6/6 identical scores on byte-identical candidate pairs.

The one open item inside the design is the relevance band's marginal value: it is required and never authoritative by construction, and the ablation that would price it is one run away. Human adjudication, the blind reviewer's delta, controlled perturbations and threshold portability are next experiments, each with the measurement that would settle it named in the report.
