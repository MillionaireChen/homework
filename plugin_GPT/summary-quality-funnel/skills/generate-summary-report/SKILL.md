---
name: generate-summary-report
description: Generate a fixed-format English Markdown report, audited statistics, and deterministic PNG charts from validated summary-quality score JSON or JSONL. Use after a batch evaluation, ranking run, benchmark, ablation, or pipeline test. The bundled code must generate every numbered section and chart; the Report Agent may author only the short Conclusion supplied back to the generator.
---

# Generate Summary Report

Run this skill inside a fresh Codex Report subagent context. Do not use Ollama or another local generative model. Run the bundled scripts to create the report. Do not manually write statistics, charts, numbered sections, or the final Markdown file.

## Required input

Require:

- validated final score JSON or JSONL;
- a report output path;
- an asset output directory.

Accept optional hard-gate drafts, embedding drafts, and an audited anchor-embedding ablation JSON.

Accept an optional corpus pair (`articles` and `summaries` JSONL) for the offline reference cross-check.

## Reference summary policy

The Report Agent is the only role permitted to read `reference_summary`, and only at this stage, after every score is final. Reporting is offline, so a reference here cannot influence a score.

Rules:

- every runtime stage stays reference-free: no hard gate, embedding gate, anchor, Scorer, or Reviewer may receive a reference summary;
- the reference is a comparator for a finished run, never a scoring input, a hidden label, or an automatic high score;
- no score may be recomputed, adjusted, or re-ranked after reading a reference;
- `scripts/reference_validation.py` derives its labels from the corpus alone and joins the score file only afterwards, so no evaluator output can influence a label;
- the report must state that references were withheld at runtime, and must present the result as agreement with weak labels rather than validated accuracy.

Omitting the corpus pair is valid and produces the four-section report.

## Workflow

1. Run `scripts/make_report_charts.py` with the score file and available routing drafts. This creates deterministic `report_stats.json` and two PNG charts.
2. When a corpus pair is supplied, run `scripts/reference_validation.py` to create `reference_validation.json` and its chart.
3. Read only `report_stats.json`, the optional `reference_validation.json`, optional audited ablation JSON, and `references/conclusion-example.md`.
4. Write one plain-text conclusion file of at most 120 English words. This is the only report prose the Agent may author. State what the results support and what they do not establish. Treat Reviewer approval as internal audit completion, not objective accuracy.
5. Run `scripts/generate_report.py` with the same inputs and `--conclusion-input`. This script deterministically regenerates the statistics and charts, renders the fixed Markdown template, inserts the conclusion, and validates the result.
6. Return the generated file paths and the script validation result. Do not edit the Markdown or PNG files after generation.

If either script fails, report the failure. Do not repair, complete, or rewrite the output manually.

## Fixed output contract

The code, not the Agent, owns:

- input counts and provenance;
- funnel outcome counts;
- score and dimension statistics;
- label and review distributions;
- highest and lowest soft-score identifiers;
- ablation figures and their deterministic comparison;
- planted-category labels, per-category detection counts, and the cross-check table;
- every chart and its relative path;
- Markdown title, headings, layout, and the 800-word limit.

The Report Agent owns only the text placed beneath the final `Conclusion` heading, which is section 4 without the cross-check and section 5 with it.

If a genuine Codex subagent is unavailable, stop instead of simulating the Report Agent with a local model.

## Commands

```bash
python3 scripts/make_report_charts.py \
  --input score.jsonl \
  --output-dir report_assets \
  --hard-gate-input hard_gate_drafts.jsonl \
  --embedding-input embedding_drafts.jsonl

python3 scripts/generate_report.py \
  --input score.jsonl \
  --report-output report.md \
  --asset-dir report_assets \
  --hard-gate-input hard_gate_drafts.jsonl \
  --embedding-input embedding_drafts.jsonl \
  --ablation-input anchor_embedding_ablation.json \
  --conclusion-input conclusion.txt
```
