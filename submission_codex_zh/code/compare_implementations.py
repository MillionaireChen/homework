#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-validate the two independent implementations of the same funnel design.

Claude side : evaluation_runs_claude/run_0820_1858/score_ranked.jsonl
GPT side    : evaluation_runs_GPT/full250_codex/score.jsonl

Both scored the same 250 pairs with no reference summary at runtime and without
seeing each other's output. This script measures how far two independent
readings of one design agree, and attributes every disagreement.

Weak labels are derived from the corpus alone (reference summaries are read
here, offline, after both runs were final) purely to characterise the
disagreements. They never influenced either run.

Outputs: cross_validation.json + three PNG charts.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = ["Hiragino Sans", "Arial Unicode MS", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False


def load_rows(path: Path) -> dict:
    return {json.loads(l)["summary_id"]: json.loads(l)
            for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}


def weak_label(sid: str, aid: str, arts: dict, sums: dict) -> str:
    """Planted-category label derived from the corpus alone."""
    a = arts[aid]
    t = sums[sid].strip()
    ref = a["reference_summary"].strip()
    if t == ref:
        return "REF_VERBATIM"
    if ref.startswith(t):
        return "REF_TRUNCATED"
    if len(t) >= 40 and t[:40] in a["text"]:
        return "ARTICLE_COPY"
    for oid, o in arts.items():
        if oid != aid and t == o["reference_summary"].strip():
            return "OFF_TOPIC"
    return "GENERATED"


def spearman(x, y) -> float:
    def rank(a):
        order = sorted(range(len(a)), key=lambda i: a[i])
        r = [0] * len(a)
        for pos, i in enumerate(order):
            r[i] = pos + 1
        return r
    rx, ry = rank(x), rank(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--claude", type=Path, required=True)
    ap.add_argument("--gpt", type=Path, required=True)
    ap.add_argument("--articles", type=Path, required=True)
    ap.add_argument("--summaries", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    C, G = load_rows(args.claude), load_rows(args.gpt)
    arts = {a["article_id"]: a for a in
            (json.loads(l) for l in args.articles.read_text(encoding="utf-8").splitlines() if l.strip())}
    sums = {s["summary_id"]: s["summary"] for s in
            (json.loads(l) for l in args.summaries.read_text(encoding="utf-8").splitlines() if l.strip())}

    ids = sorted(set(C) & set(G))
    term = lambda r: r.get("terminal_result")
    both_t = [i for i in ids if term(C[i]) and term(G[i])]
    both_s = [i for i in ids if not term(C[i]) and not term(G[i])]
    only_c = [i for i in ids if term(C[i]) and not term(G[i])]
    only_g = [i for i in ids if term(G[i]) and not term(C[i])]
    route_agree = (len(both_t) + len(both_s)) / len(ids)
    cat_agree = sum(1 for i in both_t if term(C[i]) == term(G[i]))

    cs = [C[i]["score"] for i in both_s]
    gs = [G[i]["score"] for i in both_s]
    rho = spearman(cs, gs)
    mae = sum(abs(a - b) for a, b in zip(cs, gs)) / len(both_s)

    truth = {i: weak_label(i, C[i]["article_id"], arts, sums) for i in ids}

    stats = {
        "provenance": {
            "claude_run": str(args.claude),
            "gpt_run": str(args.gpt),
            "reference_used_at_runtime_by_either": False,
            "weak_labels_derived_at": "cross-validation stage, after both runs were final",
            "implementations_saw_each_other": False,
        },
        "coverage": {"comparable_pairs": len(ids), "claude_rows": len(C), "gpt_rows": len(G)},
        "routing_agreement": {
            "both_terminal": len(both_t),
            "both_scored": len(both_s),
            "claude_only_terminal": len(only_c),
            "gpt_only_terminal": len(only_g),
            "rate": round(route_agree, 4),
            "terminal_category_agreement": {
                "compared": len(both_t), "identical": cat_agree,
                "rate": round(cat_agree / len(both_t), 4) if both_t else None,
                "mismatches": dict(Counter(f"{term(C[i])}|{term(G[i])}"
                                           for i in both_t if term(C[i]) != term(G[i]))),
            },
        },
        "score_agreement": {
            "compared": len(both_s),
            "spearman": round(rho, 4),
            "mean_absolute_difference": round(mae, 2),
            "claude_mean": round(sum(cs) / len(cs), 2),
            "gpt_mean": round(sum(gs) / len(gs), 2),
        },
        "disagreement_attribution": {
            "claude_only_terminal": {
                "count": len(only_c),
                "by_terminal_type": dict(Counter(term(C[i]) for i in only_c)),
                "by_weak_label": dict(Counter(truth[i] for i in only_c)),
                "gpt_scores_for_these": {
                    "min": min((G[i]["score"] for i in only_c), default=None),
                    "max": max((G[i]["score"] for i in only_c), default=None),
                },
            },
            "gpt_only_terminal": {
                "count": len(only_g),
                "by_terminal_type": dict(Counter(term(G[i]) for i in only_g)),
                "by_weak_label": dict(Counter(truth[i] for i in only_g)),
                "claude_scores_for_these": {
                    "min": min((C[i]["score"] for i in only_g), default=None),
                    "max": max((C[i]["score"] for i in only_g), default=None),
                },
            },
        },
        "by_weak_label": {},
    }

    for lab in ["REF_VERBATIM", "GENERATED", "REF_TRUNCATED", "ARTICLE_COPY", "OFF_TOPIC"]:
        grp = [i for i in ids if truth[i] == lab]
        if not grp:
            continue
        stats["by_weak_label"][lab] = {
            "count": len(grp),
            "claude": {"terminated": sum(1 for i in grp if term(C[i])),
                       "mean_score": round(sum(C[i]["score"] for i in grp) / len(grp), 2)},
            "gpt": {"terminated": sum(1 for i in grp if term(G[i])),
                    "mean_score": round(sum(G[i]["score"] for i in grp) / len(grp), 2)},
        }

    (args.outdir / "cross_validation.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")

    # 1. routing agreement
    fig, ax = plt.subplots(figsize=(7, 3))
    cats = ["Both terminal", "Both scored", "Claude only\nterminal", "GPT only\nterminal"]
    vals = [len(both_t), len(both_s), len(only_c), len(only_g)]
    cols = ["#15803d", "#2563eb", "#d97706", "#9333ea"]
    ax.bar(cats, vals, color=cols)
    for i, v in enumerate(vals):
        ax.text(i, v + 2, str(v), ha="center", fontweight="bold")
    ax.set_title(f"Routing agreement across two independent implementations "
                 f"({route_agree:.1%} of {len(ids)})", fontsize=11)
    fig.tight_layout(); fig.savefig(args.outdir / "routing_agreement.png", dpi=150); plt.close(fig)

    # 2. score scatter
    fig, ax = plt.subplots(figsize=(5.2, 5))
    ax.scatter(cs, gs, s=18, alpha=0.55, color="#2563eb", edgecolors="none")
    lo = min(min(cs), min(gs)) - 3
    ax.plot([lo, 100], [lo, 100], "--", color="#94a3b8", lw=1)
    ax.set_xlabel("Claude score"); ax.set_ylabel("GPT score")
    ax.set_title(f"Scores on the {len(both_s)} pairs both scored\n"
                 f"Spearman {rho:.3f}, mean |diff| {mae:.1f}", fontsize=11)
    fig.tight_layout(); fig.savefig(args.outdir / "score_agreement.png", dpi=150); plt.close(fig)

    # 3. per weak label: terminated share
    labs = list(stats["by_weak_label"])
    x = range(len(labs))
    cterm = [stats["by_weak_label"][l]["claude"]["terminated"] / stats["by_weak_label"][l]["count"] * 100 for l in labs]
    gterm = [stats["by_weak_label"][l]["gpt"]["terminated"] / stats["by_weak_label"][l]["count"] * 100 for l in labs]
    fig, ax = plt.subplots(figsize=(8, 3.4))
    ax.bar([i - 0.2 for i in x], cterm, 0.4, label="Claude", color="#2563eb")
    ax.bar([i + 0.2 for i in x], gterm, 0.4, label="GPT", color="#f59e0b")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{l}\n(n={stats['by_weak_label'][l]['count']})" for l in labs], fontsize=8)
    ax.set_ylabel("% terminated"); ax.set_ylim(0, 108); ax.legend()
    ax.set_title("Termination rate per planted category (weak labels, offline)", fontsize=11)
    fig.tight_layout(); fig.savefig(args.outdir / "termination_by_category.png", dpi=150); plt.close(fig)

    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
