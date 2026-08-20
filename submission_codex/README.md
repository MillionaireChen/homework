# Summary-quality evaluator — Codex submission

This directory is the Codex implementation submitted for the LLM Application Evaluation Design take-home assignment. It evaluates 250 Japanese news-article summaries (five candidates for each of 50 articles) and writes one JSON object per `summary_id` to [`scores.jsonl`](scores.jsonl).

## Reproduction through the plugins

Both implementations were run as plugins, not as standalone scripts. To reproduce the Codex side, install [`code/summary-quality-funnel`](code/summary-quality-funnel) in Codex, make the supplied `data/` directory available, and invoke the installed skill with the slash command:

```text
/summary-quality-funnel:evaluate-summary-quality
```

The command starts the full funnel and writes the JSONL, audit traces, charts, and report. The Claude side was run independently from the Claude plugin source in `../plugin_claude/summary-quality-funnel` with:

```text
/summary-quality-funnel:evaluate-summaries
```

The two plugins were installed and invoked separately; neither implementation read the other’s outputs during scoring. The comparison in [`run_artifacts/cross_validation.json`](run_artifacts/cross_validation.json) was a later offline step over the two completed JSONL files. The bundled Python files are supporting validation/report code used by the plugins, not the primary user-facing entry point.

The report figures are generated deterministically from the final JSONL. Editable architecture and funnel diagrams are provided as [`pipeline.drawio`](diagrams/pipeline.drawio) and [`funnel.drawio`](diagrams/funnel.drawio); the PNGs in `figures/` are the report charts generated from the JSONL.

The independent Claude implementation is compared with this Codex implementation in [`run_artifacts/cross_validation.json`](run_artifacts/cross_validation.json). The comparison script is [`code/compare_implementations.py`](code/compare_implementations.py); it reads only final outputs and derives weak reference labels after both runs are complete.

## AI-tool disclosure

Codex agents performed the Grounding Gate, Scorer, Reviewer, and Report roles. A local embedding endpoint was used only for article-assigned relevance evidence; no local generative model and no reference summary were provided to runtime evaluators. The evaluation design, hard/soft constraint split, terminal policy, and validation checks were human-directed decisions refined with AI assistance.

## Output schema

Each row contains the article and summary identifiers, terminal or soft score, dimensions, quality label, evidence, review decision, and an evaluation trace. Terminal records receive score 0 and a terminal rank; soft records sum faithfulness (50), coverage (30), coherence (15), and conciseness (5).
