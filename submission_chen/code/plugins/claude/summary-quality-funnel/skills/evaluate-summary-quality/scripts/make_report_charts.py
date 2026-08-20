#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fixed report charts from a ranked funnel output JSONL.

Reads the funnel's ranked results and emits three deterministic charts
plus a stats JSON (stdout) for the summary-reporter agent:
  1. funnel.png            — stage-by-stage survival funnel
  2. scores_by_article.png — per-article grouped score bars
  3. categories.png        — outcome category counts
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = ["Hiragino Sans", "Arial Unicode MS", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

TERMINAL_COLORS = {
    "FACTUAL_REVERSAL": "#7f1d3d",
    "FABRICATED_CONTENT": "#9d174d",
    "OFF_TOPIC": "#b91c1c",
    "VERBATIM_SOURCE_COPY": "#c2410c",
    "OBVIOUS_TRUNCATION": "#d97706",
    "OVER_SENTENCE_LIMIT": "#a16207",
    "EMPTY_OUTPUT": "#7f1d1d",
}
LABEL_COLORS = {
    "EXCELLENT": "#15803d", "GOOD": "#65a30d", "FINE": "#84cc16",
    "MIXED": "#ca8a04", "POOR": "#dc2626",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="ranked JSONL")
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    rows = [json.loads(l) for l in args.input.read_text(encoding="utf-8").splitlines() if l.strip()]
    total = len(rows)
    terminals = Counter(r["terminal_result"] for r in rows if r["terminal_result"])
    soft = [r for r in rows if r["eligible_for_soft_scoring"]]
    labels = Counter(r["quality_label"] for r in soft)
    hard_stage = sum(1 for r in rows if r["terminal_result"] and not any(
        e.get("stage") == "embedding_relevance" for e in r["evaluation_trace"]))
    offtopic = terminals.get("OFF_TOPIC", 0)
    rerouted = sum(1 for r in rows if any(
        e.get("stage") == "early_stop" and isinstance(e.get("evidence"), dict)
        and e["evidence"].get("rerouted_by") for e in r["evaluation_trace"]))

    # 1. funnel
    stages = [("Input pairs", total),
              ("Passed string gates", total - hard_stage),
              ("Passed relevance gate", total - hard_stage - offtopic),
              ("Soft-scored", len(soft))]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    names = [s[0] for s in stages][::-1]
    vals = [s[1] for s in stages][::-1]
    ax.barh(names, vals, color=["#15803d", "#2563eb", "#2563eb", "#64748b"])
    for i, v in enumerate(vals):
        ax.text(v + 0.2, i, str(v), va="center", fontsize=11, fontweight="bold")
    ax.set_xlim(0, total * 1.12)
    ax.set_title("Cascade funnel: survivors per stage", fontsize=12)
    fig.tight_layout(); fig.savefig(args.outdir / "funnel.png", dpi=150); plt.close(fig)

    # 2. per-article grouped scores
    byart = defaultdict(list)
    for r in rows:
        byart[r["article_id"]].append(r)
    fig, ax = plt.subplots(figsize=(9, 3.6))
    x, heights, colors, seps = [], [], [], []
    pos = 0
    ticks, ticklabels = [], []
    for aid, group in byart.items():
        group = sorted(group, key=lambda g: g["rank_within_article"])
        start = pos
        for r in group:
            x.append(pos); heights.append(r["score"])
            c = (TERMINAL_COLORS.get(r["terminal_result"])
                 or LABEL_COLORS.get(r["quality_label"], "#64748b"))
            colors.append(c); pos += 1
        ticks.append((start + pos - 1) / 2)
        ticklabels.append(str(aid)[:12])
        pos += 1
    ax.bar(x, heights, color=colors)
    ax.set_xticks(ticks); ax.set_xticklabels(ticklabels, fontsize=9)
    ax.set_ylabel("score"); ax.set_ylim(0, 105)
    ax.set_title("Scores per article (ordered by within-article rank; red/orange = terminal)", fontsize=12)
    fig.tight_layout(); fig.savefig(args.outdir / "scores_by_article.png", dpi=150); plt.close(fig)

    # 3. category counts
    cats = dict(labels)
    for k, v in terminals.items():
        cats[k] = v
    order = ["EXCELLENT", "GOOD", "FINE", "MIXED", "POOR",
             "OBVIOUS_TRUNCATION", "VERBATIM_SOURCE_COPY", "OFF_TOPIC",
             "FACTUAL_REVERSAL", "FABRICATED_CONTENT",
             "OVER_SENTENCE_LIMIT", "EMPTY_OUTPUT"]
    keys = [k for k in order if cats.get(k)]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.bar(keys, [cats[k] for k in keys],
           color=[LABEL_COLORS.get(k) or TERMINAL_COLORS.get(k, "#64748b") for k in keys])
    for i, k in enumerate(keys):
        ax.text(i, cats[k] + 0.08, str(cats[k]), ha="center", fontweight="bold")
    ax.set_title("Outcome category distribution", fontsize=12)
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=8)
    fig.tight_layout(); fig.savefig(args.outdir / "categories.png", dpi=150); plt.close(fig)

    stats = {
        "total": total,
        "hard_gate_intercepted": hard_stage,
        "off_topic_intercepted": offtopic,
        "reviewer_rerouted": rerouted,
        "soft_scored": len(soft),
        "terminals": dict(terminals),
        "soft_labels": dict(labels),
        "soft_score_min": min((r["score"] for r in soft), default=None),
        "soft_score_max": max((r["score"] for r in soft), default=None),
        "articles": len(byart),
        "charts": ["funnel.png", "scores_by_article.png", "categories.png"],
    }
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
