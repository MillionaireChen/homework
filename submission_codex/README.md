# Summary-quality evaluator — Codex submission

This directory is the Codex implementation submitted for the LLM Application Evaluation Design take-home assignment. It evaluates 250 Japanese news-article summaries (five candidates for each of 50 articles) and writes one JSON object per `summary_id` to [`scores.jsonl`](scores.jsonl).

## Reproduction

The source used for the run is under [`code/summary-quality-funnel`](code/summary-quality-funnel). The run was executed on the supplied `data/articles.jsonl` and `data/summaries.jsonl` using the four-stage funnel described in [`report.md`](report.md): deterministic hard gates, assigned-article embedding evidence, Grounding Gate, and Scorer/Reviewer agents. The final file was schema-validated and ranked within each article.

The report figures are generated deterministically from the final JSONL. Editable architecture and funnel diagrams are provided as [`pipeline.drawio`](diagrams/pipeline.drawio) and [`funnel.drawio`](diagrams/funnel.drawio); the PNGs in `figures/` are the report charts generated from the JSONL.

## AI-tool disclosure

Codex agents performed the Grounding Gate, Scorer, Reviewer, and Report roles. A local embedding endpoint was used only for article-assigned relevance evidence; no local generative model and no reference summary were provided to runtime evaluators. The evaluation design, hard/soft constraint split, terminal policy, and validation checks were human-directed decisions refined with AI assistance.

## Output schema

Each row contains the article and summary identifiers, terminal or soft score, dimensions, quality label, evidence, review decision, and an evaluation trace. Terminal records receive score 0 and a terminal rank; soft records sum faithfulness (50), coverage (30), coherence (15), and conciseness (5).
