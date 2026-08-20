# -*- coding: utf-8 -*-
"""组装漏斗最终结果: 硬约束终止 + 跑题终止 + 软评分, 按 output-schema 输出 JSONL。"""
import json, glob, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
def J(p): return json.load(open(os.path.join(HERE, p), encoding="utf-8"))
def JL(p): return [json.loads(l) for l in open(os.path.join(HERE, p), encoding="utf-8") if l.strip()]

hard = {r["summary_id"]: r for r in JL("funnel_25_hard.jsonl")}
emb = {r["summary_id"]: r for r in JL("funnel_25_emb.jsonl")}
terminals = J("tmp/reviewer_terminals.json")
scorers = {}
for p in glob.glob(os.path.join(HERE, "tmp/scorer_*.json")):
    d = json.load(open(p, encoding="utf-8"))
    scorers[d["article_id"]] = d
soft_reviews = {}
for p in glob.glob(os.path.join(HERE, "tmp/reviewer_soft_*.json")):
    soft_reviews.update(json.load(open(p, encoding="utf-8")))

TERMINAL_RANK = {"OFF_TOPIC": 0, "EMPTY_OUTPUT": 0, "VERBATIM_SOURCE_COPY": 1,
                 "OBVIOUS_TRUNCATION": 2, "OVER_SENTENCE_LIMIT": 3}

out = []
for sid, h in hard.items():
    aid = h["article_id"]
    base = {"article_id": aid, "summary_id": sid}
    trace = [e for e in h.get("evaluation_trace", [])]
    tdec = terminals.get(sid)

    if h["hard_fail"] and tdec and tdec["decision"] == "APPROVE":
        tr = h["draft_terminal_result"]
        trace.append({"stage": "independent_review", "result": "APPROVE",
                      "evidence": tdec["evidence"]})
        trace.append({"stage": "early_stop",
                      "result": tr,
                      "evidence": {"skipped_stages": ["embedding_relevance", "soft_scoring"]}})
        out.append({**base, "eligible_for_soft_scoring": False, "score": 0,
                    "terminal_result": tr, "terminal_rank": TERMINAL_RANK[tr],
                    "quality_label": tr, "hard_fail": True, "hard_fail_reason": tr,
                    "dimensions": None,
                    "review": {"decision": "APPROVE", "rounds": 1, "confidence": "HIGH",
                               "findings": [tdec["evidence"]]},
                    "evaluation_trace": trace})
        continue

    e = emb.get(sid)
    if e:
        trace = [ev for ev in e.get("evaluation_trace", [])]
    if e and e["embedding_evidence"]["off_topic_suspect"] and tdec and tdec["decision"] == "APPROVE":
        trace.append({"stage": "independent_review", "result": "APPROVE",
                      "evidence": tdec["evidence"]})
        trace.append({"stage": "early_stop", "result": "OFF_TOPIC",
                      "evidence": {"skipped_stages": ["soft_scoring"]}})
        out.append({**base, "eligible_for_soft_scoring": False, "score": 0,
                    "terminal_result": "OFF_TOPIC", "terminal_rank": 0,
                    "quality_label": "OFF_TOPIC", "hard_fail": True,
                    "hard_fail_reason": "OFF_TOPIC", "dimensions": None,
                    "review": {"decision": "APPROVE", "rounds": 1, "confidence": "HIGH",
                               "findings": [tdec["evidence"]]},
                    "evaluation_trace": trace})
        continue

    sc = scorers.get(aid, {}).get("candidates", {}).get(sid)
    if not sc:
        print(f"WARN: no scorer result for {sid}", file=sys.stderr)
        continue
    rev = soft_reviews.get(sid, {})

    # Reviewer ESCALATE 且认定为物理截断 → 按其判定改道至截断硬门终止
    if rev.get("decision") == "ESCALATE" and any(
        "截断" in f or "TRUNCAT" in f.upper() for f in rev.get("findings", [])
    ):
        trace.append({"stage": "independent_review", "result": "ESCALATE_TO_TERMINAL",
                      "evidence": rev.get("findings", [])})
        trace.append({"stage": "early_stop", "result": "OBVIOUS_TRUNCATION",
                      "evidence": {"rerouted_by": "soft-score reviewer",
                                   "skipped_stages": []}})
        out.append({**base, "eligible_for_soft_scoring": False, "score": 0,
                    "terminal_result": "OBVIOUS_TRUNCATION", "terminal_rank": 2,
                    "quality_label": "OBVIOUS_TRUNCATION", "hard_fail": True,
                    "hard_fail_reason": "OBVIOUS_TRUNCATION", "dimensions": None,
                    "review": {"decision": "APPROVE", "rounds": 2, "confidence": "HIGH",
                               "findings": rev.get("findings", [])},
                    "evaluation_trace": trace})
        continue
    dims = sc["dimensions"]
    findings = rev.get("findings", [])
    rounds = 1
    if rev.get("decision") == "REVISE" and rev.get("suggested_dimensions"):
        dims = rev["suggested_dimensions"]
        rounds = 2
    score = sum(dims.values())
    label = ("EXCELLENT" if score >= 90 else "GOOD" if score >= 75
             else "MIXED" if score >= 50 else "POOR")
    decision = "APPROVE" if rev.get("decision") in ("APPROVE", "REVISE") else \
               rev.get("decision", "APPROVE")
    confidence = rev.get("confidence", "MEDIUM")
    trace.append({"stage": "draft_scoring", "result": "DRAFT",
                  "evidence": {"draft_dimensions": sc["dimensions"]}})
    trace.append({"stage": "independent_review", "result": rev.get("decision", "APPROVE"),
                  "evidence": findings})
    out.append({**base, "eligible_for_soft_scoring": True, "score": score,
                "terminal_result": None, "terminal_rank": None,
                "quality_label": label, "hard_fail": False, "hard_fail_reason": None,
                "dimensions": dims,
                "anchor": scorers.get(aid, {}).get("anchor"),
                "claim_checks": sc.get("claim_checks", []),
                "issues": sc.get("issues", []),
                "review": {"decision": decision, "rounds": rounds,
                           "confidence": confidence, "findings": findings},
                "evaluation_trace": trace})

path = os.path.join(HERE, "funnel_25_scores.jsonl")
open(path, "w", encoding="utf-8").write(
    "\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n")
print(f"assembled {len(out)} records -> {path}")
