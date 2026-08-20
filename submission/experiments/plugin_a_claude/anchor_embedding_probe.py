# -*- coding: utf-8 -*-
"""
锚点 embedding 对比实验(用户提出):
对同一批候选摘要计算两组相似度——
  sim_article = 摘要 ↔ 文章全文(title + text[:1500], 现行门禁用法)
  sim_anchor  = 摘要 ↔ 锚点(scorer 生成的 main_event + key_facts + anchor_summary)
然后与漏斗的大模型软评分算 Spearman 相关, 回答:
"有锚点环节 vs 没有锚点环节, embedding 信号质量差多少"。
"""
import json, glob, os
import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OLLAMA = "http://localhost:11434/api/embed"
MODEL = "qwen3-embedding:0.6b"

def embed(texts):
    r = requests.post(OLLAMA, json={"model": MODEL, "input": texts,
                                    "options": {"num_ctx": 4096}}, timeout=600)
    r.raise_for_status()
    v = np.array(r.json()["embeddings"], dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)

def spearman(x, y):
    def rank(a):
        order = np.argsort(a)
        r = np.empty(len(a)); r[order] = np.arange(1, len(a) + 1)
        return r
    rx, ry = rank(np.array(x)), rank(np.array(y))
    return float(np.corrcoef(rx, ry)[0, 1])

rows = [json.loads(l) for l in open(os.path.join(HERE, "funnel_25_input.jsonl"), encoding="utf-8")]
anchors = {}
for p in glob.glob(os.path.join(HERE, "tmp/scorer_*.json")):
    d = json.load(open(p, encoding="utf-8"))
    a = d["anchor"]
    anchors[d["article_id"]] = a["main_event"] + "\n" + "\n".join(a["key_facts"]) + "\n" + a["anchor_summary"]
scores = {r["summary_id"]: r for r in
          (json.loads(l) for l in open(os.path.join(HERE, "funnel_25_scores.jsonl"), encoding="utf-8"))}

aids = sorted({r["article_id"] for r in rows})
art_vec = dict(zip(aids, embed([next(r["title"] + "\n" + r["article"][:1500] for r in rows if r["article_id"] == a) for a in aids])))
anc_vec = dict(zip(aids, embed([anchors[a] for a in aids])))
sum_vecs = embed([r["summary"] for r in rows])

print(f"{'summary_id':<22}{'sim全文':>8}{'sim锚点':>8}{'漏斗分':>7}  状态")
print("-" * 66)
soft_a, soft_n, soft_s = [], [], []
for r, v in zip(rows, sum_vecs):
    sa = float(v @ art_vec[r["article_id"]])
    sn = float(v @ anc_vec[r["article_id"]])
    rec = scores.get(r["summary_id"], {})
    s = rec.get("score")
    tag = rec.get("terminal_result") or rec.get("quality_label", "?")
    print(f"{r['summary_id']:<26}{sa:>8.3f}{sn:>8.3f}{str(s):>7}  {tag}")
    if rec.get("eligible_for_soft_scoring"):
        soft_a.append(sa); soft_n.append(sn); soft_s.append(s)

print("-" * 66)
print(f"仅软评分条目 n={len(soft_s)}:")
print(f"  Spearman(sim全文, 漏斗分) = {spearman(soft_a, soft_s):+.3f}")
print(f"  Spearman(sim锚点, 漏斗分) = {spearman(soft_n, soft_s):+.3f}")
