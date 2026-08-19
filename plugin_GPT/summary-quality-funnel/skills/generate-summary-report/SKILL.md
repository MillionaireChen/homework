---
name: generate-summary-report
description: Generate a concise, audited English Markdown report and deterministic PNG charts from validated summary-quality score JSON or JSONL. Use after a batch evaluation, ranking run, benchmark, ablation, or pipeline test when readers need input provenance, funnel outcomes, score statistics, reviewer corrections, limitations, and a calibrated conclusion without inspecting machine-readable records.
---

# Generate Summary Report

Act as the dedicated Report Agent for the summary-quality funnel. Convert validated machine output into a short report for readers who will not inspect JSON or JSONL.

## Required input

Require:

- Final score JSON or JSONL containing one record per article-summary pair.
- An output directory.

Accept optional batch metadata, hard-gate drafts, embedding drafts, and audited ablation findings. Never require or inspect `reference_summary`.

## Workflow

1. Run `scripts/make_report_charts.py` on the final score file. Pass hard-gate and embedding draft files when available so the statistics distinguish initial gate proposals from downstream recoveries.
2. Read the generated `report_stats.json`. Treat it as the only source for counts and aggregates.
3. Read `references/report-example.md` and follow its structure and level of detail.
4. Write one English Markdown report with exactly these level-two sections:
   - `## 1. Input Data`
   - `## 2. Funnel Outcomes`
   - `## 3. Results`
   - `## 4. Conclusion`
5. Embed both deterministic charts with relative Markdown paths.
6. State a calibrated verdict. A small successful run may establish a `usable prototype that needs broader validation`; it cannot establish production readiness.
7. Run `scripts/validate_report.py`. Do not deliver a report that fails structure, image, or length validation.

## Reporting rules

- Keep the complete report below 800 words.
- Use only audited statistics and Reviewer-confirmed findings.
- Report how many pairs completed soft scoring, how many stopped, and why.
- Include score range, central tendency, label distribution, and Reviewer revision count when available.
- Call out both a representative success and a representative failure only when evidence was supplied.
- Do not infer correctness from semantic similarity alone.
- Do not expose chain-of-thought.
- Do not browse or expand the corpus while reporting.

Autonomous web corpus expansion is a separate future capability. It requires an explicit user request, source provenance, licensing review, deduplication, and a separate evaluation protocol.

## Commands

```bash
python3 scripts/make_report_charts.py \
  --input score.jsonl \
  --output-dir report_assets \
  --hard-gate-input hard_gate_drafts.jsonl \
  --embedding-input embedding_drafts.jsonl

python3 scripts/validate_report.py report.md --max-words 800
```
