# `code/` — what is here and why

**The code is the plugin.** The evaluator is not a script that happens to be
packaged; the two directories under `plugins/` *are* the evaluator, and
everything else here either informed them or checks them.

## `plugins/a-claude-code/` — PRIMARY

The Claude Code plugin that produced the submitted `scores.jsonl`.

```
.claude-plugin/marketplace.json           local marketplace declaration
summary-quality-funnel/
  .claude-plugin/plugin.json              manifest, v0.2.0
  commands/evaluate-summaries.md          the slash command (entry point)
  agents/
    summary-grounding-gate.md             layer-2 semantic gate; no score, no rubric
    summary-scorer.md                     anchor + claim checks + four dimensions
    summary-reviewer.md                   confirms every terminal, audits every score
    summary-reviewer-blind.md             structurally reference-blind variant (shipped, unused — see report §IV-C)
    summary-reporter.md                   the only role permitted to read reference_summary
  skills/evaluate-summary-quality/
    SKILL.md                              the workflow the command follows
    references/rubric.md                  hard constraints, soft dimensions, bands
    references/agent-prompts.md           per-role contracts
    references/few-shot-examples.md       one condition-matched example per route
    references/output-schema.md           the record schema
    references/embedding-calibration.md   how 0.50 was derived, and its caveats
    scripts/hard_gate.py                  layer 1: copy, sentence count, truncation evidence
    scripts/embedding_gate.py             own-article similarity only; never terminal
    scripts/rank_results.py               within-article ranking incl. terminal tiers
    scripts/validate_result.py            schema + arithmetic + band validation
    scripts/reference_validation.py       offline weak-label cross-check (report stage only)
    scripts/make_report_charts.py         deterministic charts from validated JSONL
```

Read `references/rubric.md` and `references/agent-prompts.md` first — between
them they contain every rule the design applies and every constraint each role
operates under.

## `plugins/b-codex/` — SECONDARY

The same design implemented for Codex, with reporting split into its own
first-class skill. It shares no code path with the primary plugin and was not
used to produce `scores.jsonl`; it exists so the *design* can be checked
against a second implementation (report §III-F).

## `runs/`

Complete audit trails, not just outputs.

- `primary_claude_full250/` — the submitted run. `score_ranked.jsonl` is
  byte-identical to `../../scores.jsonl`. Also: `inputs.jsonl` (what the
  Reviewer actually received — note the absence of any reference field),
  `hard_gate_drafts.jsonl`, `embedding_evidence.jsonl`,
  every per-batch agent input and output under `*_batches/` and `*_outputs/`,
  `run_manifest.json` (stage-by-stage counts), and the generated `report.md`.
- `secondary_codex_full250/` — the same for the Codex run.

Every intermediate is kept deliberately, including the batches where a
Reviewer rejected a gate proposal. Those are the interesting ones.

## `exploration/`

The probes that came before the design, with their raw outputs.

| File | What it established |
|---|---|
| `build_viewer.py` → `dataset_viewer.html` | side-by-side article/candidate reader; this is what exposed the five populations |
| `ref_hit_stats.py`, `ref_hit_log.txt`, `ref_copies.json` | the corpus census by string comparison |
| `sieve.json` | the resulting per-candidate categorisation |
| `offtopic_probe_embedding.py` → `offtopic_embedding.json` | embedding relevance over all 250 pairs |
| `offtopic_probe_reranker.py` → `offtopic_reranker.json` | **the rejected cross-encoder** — kept because the rejection is evidence |
| `refvsbad_sim_10articles.txt`, `refvsbad_sim_random10.txt` | the two disjoint threshold-calibration probes |
| `rank.py`, `rank_probe_10articles.txt` | within-article ranking behaviour |
| `dup.py` | the duplicate-text groups used in report §III-B and §III-C |
| `anchor_embedding_probe.py`, `anchor_probe_log.txt` | **the rejected anchor-similarity feature** |
| `generated_109_scores.csv`, `ref_hit_vs_codex.json` | the unlabelled block, tabulated |
| `prototypes/` | the abandoned 25-pair and 50-pair funnels that preceded the plugin |

These are scratch files, kept as evidence of how the work actually went rather
than tidied for publication. Their hard-coded paths assume they are run from
the assignment repository root with `explore/` and `evaluation_runs_*/` in
place, which is where they ran. `validation/verify_report_numbers.py` is the
one script here written to run from its own directory against the submitted
layout.

## `validation/`

- `verify_report_numbers.py` — re-derives all 91 numbers quoted in the report
  from `data/` and the two run files, and asserts each one. Run it with no
  arguments from this directory.
- `compare_implementations.py` — the cross-host comparison of §III-F.
- `third_read_109_unlabelled/` — the third independent scoring of the 109
  candidates with no derivable ground truth (§III-G), with its `agreement.json`.

## `report/`

`report.tex` and its build. All diagrams are TikZ and all charts are pgfplots
drawn from the run data; there are no imported images.

## The logs

- `DESIGN.md` — the design specification as it currently stands.
- `processing.md` — the dated Claude-side decision log. It records the
  reversals too: the reference-based comparator that was removed, the
  batch-relative relevance evidence that was ruled inadmissible, the
  `FACTUAL_REVERSAL` rule that was first routed through soft scoring and then
  promoted to its own gate, and the truncation smoke test whose result
  contradicted the fix that preceded it.
- `progressing_GT.md` — the Codex-side implementation log.
