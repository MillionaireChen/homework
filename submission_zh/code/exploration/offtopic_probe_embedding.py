# -*- coding: utf-8 -*-
"""
跑题门禁探针(embedding 版)
模型: Ollama qwen3-embedding:0.6b
方法: 250 条摘要 × 50 篇文章余弦相似度矩阵。
     每条摘要输出: own_sim(与自己文章), own_rank(自己文章在50篇中的检索排名),
     top1(排第一的文章), margin(own_sim - 最强他篇)。
判定思路: 正常摘要 own_rank 应为 1;跑题摘要的 top1 会是别的文章(margin<0)。
"""
import json, os, sys
import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OLLAMA = "http://localhost:11434/api/embed"
MODEL = "qwen3-embedding:0.6b"

articles = [json.loads(l) for l in open(os.path.join(DATA, "articles.jsonl"), encoding="utf-8")]
summaries = [json.loads(l) for l in open(os.path.join(DATA, "summaries.jsonl"), encoding="utf-8")]

def embed(texts, batch=25):
    vecs = []
    for i in range(0, len(texts), batch):
        r = requests.post(OLLAMA, json={
            "model": MODEL,
            "input": texts[i:i+batch],
            "options": {"num_ctx": 4096},
        }, timeout=600)
        r.raise_for_status()
        vecs.extend(r.json()["embeddings"])
        print(f"  embedded {min(i+batch, len(texts))}/{len(texts)}", file=sys.stderr)
    v = np.array(vecs, dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)

print("embedding articles (title + text[:1500]) ...", file=sys.stderr)
art_texts = [a["title"] + "\n" + a["text"][:1500] for a in articles]
A = embed(art_texts)
print("embedding summaries ...", file=sys.stderr)
S = embed([s["summary"] for s in summaries])

sim = S @ A.T  # 250 x 50
art_ids = [a["article_id"] for a in articles]
art_idx = {aid: i for i, aid in enumerate(art_ids)}
art_title = {a["article_id"]: a["title"] for a in articles}

rows = []
for i, s in enumerate(summaries):
    own = art_idx[s["article_id"]]
    own_sim = float(sim[i, own])
    order = np.argsort(-sim[i])
    own_rank = int(np.where(order == own)[0][0]) + 1
    top1 = art_ids[int(order[0])]
    others = np.delete(sim[i], own)
    margin = own_sim - float(others.max())
    rows.append({
        "summary_id": s["summary_id"],
        "own_sim": round(own_sim, 4),
        "own_rank": own_rank,
        "margin": round(margin, 4),
        "top1_article": top1,
    })

json.dump(rows, open(os.path.join(HERE, "offtopic_embedding.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

rank1 = [r for r in rows if r["own_rank"] == 1]
flagged = [r for r in rows if r["own_rank"] > 1]
print(f"\n=== 结果(qwen3-embedding:0.6b)===")
print(f"own_rank=1(检索到自己文章): {len(rank1)}/250")
print(f"own_rank>1(疑似跑题): {len(flagged)}/250\n")

ms = sorted(r["margin"] for r in rank1)
print(f"rank=1 组 margin 分位数: p5={ms[int(len(ms)*.05)]:.3f} p25={ms[int(len(ms)*.25)]:.3f} "
      f"p50={ms[len(ms)//2]:.3f}")
print(f"rank=1 组 own_sim 最小值: {min(r['own_sim'] for r in rank1):.3f}")
if flagged:
    print(f"rank>1 组 own_sim 最大值: {max(r['own_sim'] for r in flagged):.3f}\n")
print("疑似跑题名单(按 margin 从低到高):")
for r in sorted(flagged, key=lambda x: x["margin"]):
    print(f"  {r['summary_id']}  own_sim={r['own_sim']:.3f} rank={r['own_rank']} "
          f"margin={r['margin']:+.3f}  top1={r['top1_article']} «{art_title[r['top1_article']][:24]}»")
