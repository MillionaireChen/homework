# Summary Quality Funnel — Submission

This submission evaluates 250 Japanese news summaries with one reference-free design implemented twice as installable plugins. The **Claude Code plugin is the primary implementation** and produces the submitted [`scores.jsonl`](scores.jsonl). The **Codex plugin is a secondary independent implementation** used to test whether the design survives a different agent host.

## Submission contents

```text
submission_chen/
├── README.md
├── report.pdf                       # primary 4-page IEEE conference report
├── report.tex                       # editable LaTeX source
├── report.md                        # earlier text-source companion
├── scores.jsonl                     # primary Claude-plugin output, 250 rows
├── requirements.txt
├── code/
│   ├── plugins/
│   │   ├── claude/                  # primary installable plugin
│   │   └── codex/                   # secondary installable plugin
│   ├── exploration/                 # exploratory probes and logs
│   ├── validation/                  # cross-implementation comparison
│   └── figures/                     # Draw.io-to-SVG renderer
├── runs/
│   ├── claude_primary/              # primary scores, manifest, report, statistics
│   └── codex_secondary/             # independent scores, report, statistics
├── validation/                      # cross-implementation statistics
└── figures/                         # editable Draw.io sources + rendered SVGs
```

The supplied assignment `data/` directory is not duplicated. Place `submission_chen/` beside `data/`, as in the provided repository.

## Read or rebuild the report

[`report.pdf`](report.pdf) is the primary report artifact. It follows the IEEE conference two-column format and covers the required Exploration, Design, Validation, and Limitations sections. Its diagrams are native TikZ vector graphics; validation charts are generated from the final JSONL outputs.

With a TeX Live installation that includes `IEEEtran`, rebuild it from this directory with:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error report.tex
```

No bibliography or external references are required because the report's evidence comes from the supplied dataset, the two Plugin runs, and the included local experiments.

## Run the primary Claude Code plugin

Prerequisites:

- Claude Code with local plugins enabled;
- Python 3.9+;
- Ollama serving `qwen3-embedding:0.6b` locally.

From the assignment repository root, register and install the bundled local marketplace (replace the path with the absolute path on your machine):

```bash
claude plugin marketplace add "<repository>/submission_chen/code/plugins/claude"
claude plugin install summary-quality-funnel@local
```

An equivalent project configuration example is included at [`code/plugins/claude/settings.json.example`](code/plugins/claude/settings.json.example). Then open Claude Code and invoke:

```text
/summary-quality-funnel:evaluate-summaries data/articles.jsonl data/summaries.jsonl; evaluate all 250 pairs, rank five candidates per article, and write score.jsonl and report.md
```

The slash command is the user-facing entry point. It loads the Skill, runs deterministic scripts, launches isolated Grounding Gate, Scorer, Reviewer, and Reporter roles, validates the result, ranks candidates, and produces the report. The runtime input contains only each assigned article and candidate; references are available only to the post-score report cross-check.

## Run the secondary Codex plugin

Install the local plugin directory [`code/plugins/codex/summary-quality-funnel`](code/plugins/codex/summary-quality-funnel) through Codex's plugin manager, then invoke:

```text
/summary-quality-funnel:evaluate-summary-quality data/articles.jsonl data/summaries.jsonl; evaluate the full 250-pair dataset and produce ranked score JSONL and a report
```

This is an independent implementation of the same design. It is not required to produce the primary submission score file; it is included as validation evidence. Its Report Skill deterministically generates the fixed report structure and charts; the Report Agent authors only the final conclusion.

## Reproduce the cross-implementation comparison

After both plugin runs are final:

```bash
python code/validation/compare_implementations.py \
  --claude runs/claude_primary/score_ranked.jsonl \
  --gpt runs/codex_secondary/score_ranked.jsonl \
  --articles ../data/articles.jsonl \
  --summaries ../data/summaries.jsonl \
  --outdir validation
```

This comparison happens **after** scoring. Neither plugin reads the other implementation's output, and references are not used by either runtime evaluator.

## Score format

Each JSONL row contains at least:

- `summary_id`, `article_id`, `score`, `quality_label`, and `rank_within_article`;
- either a reviewed terminal result or four soft dimensions;
- source-grounded claim checks and evidence;
- the independent review decision;
- an `evaluation_trace` recording the route actually taken.

For soft-scored summaries, `faithfulness /50 + coverage /30 + coherence /15 + conciseness /5 = score`. Reviewer-confirmed unusable outputs receive score 0 and a terminal tier so different failure modes remain auditable.

## AI-tool disclosure

I chose the production constraint, failure taxonomy, hard/soft separation, rubric weights, agent boundaries, early-stop policy, and validation strategy. Claude Code and Codex were used to inspect examples, execute isolated Grounding/Scorer/Reviewer/Reporter roles, draft structured evidence, and implement supporting scripts. A local model was used only for embeddings. Reference summaries were withheld from runtime scoring and used only for offline validation after scores were final.
