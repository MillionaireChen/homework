# -*- coding: utf-8 -*-
"""
跑题门禁探针(reranker / cross-encoder 版)
模型: BAAI/bge-reranker-v2-m3(多语言,支持日语)
方法: 每条摘要算两个相关分:
  score_own   = rerank(摘要, 自己的文章)
  score_other = rerank(摘要, embedding探针认为最像的那篇他文)
  ce_margin   = score_own - score_other
判定: 完全无关的摘要 score_own 低、ce_margin 为负。
与 offtopic_embedding.json 的结果对照分离度。
"""
import json, os, sys
from sentence_transformers import CrossEncoder

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

articles = {a["article_id"]: a for a in
            (json.loads(l) for l in open(os.path.join(DATA, "articles.jsonl"), encoding="utf-8"))}
summaries = [json.loads(l) for l in open(os.path.join(DATA, "summaries.jsonl"), encoding="utf-8")]
emb = {r["summary_id"]: r for r in
       json.load(open(os.path.join(HERE, "offtopic_embedding.json"), encoding="utf-8"))}

def art_text(aid):
    a = articles[aid]
    return a["title"] + "\n" + a["text"][:800]

model = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=512)

pairs, meta = [], []
for s in summaries:
    r = emb[s["summary_id"]]
    other = r["top1_article"] if r["top1_article"] != s["article_id"] else None
    if other is None:
        # embedding top1 是自己 → 取一个固定的对照他篇(列表中下一篇)
        ids = list(articles)
        other = ids[(ids.index(s["article_id"]) + 1) % len(ids)]
    pairs.append([s["summary"], art_text(s["article_id"])])
    pairs.append([s["summary"], art_text(other)])
    meta.append((s["summary_id"], other))

print(f"scoring {len(pairs)} pairs ...", file=sys.stderr)
scores = model.predict(pairs, batch_size=16, show_progress_bar=True)

rows = []
for i, (sid, other) in enumerate(meta):
    own, oth = float(scores[2*i]), float(scores[2*i+1])
    rows.append({"summary_id": sid, "ce_own": round(own, 4),
                 "ce_other": round(oth, 4), "ce_margin": round(own - oth, 4),
                 "other_article": other})

json.dump(rows, open(os.path.join(HERE, "offtopic_reranker.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# 与 embedding 探针的判定对照(embedding 判无关 = margin < -0.15)
emb_flag = {sid for sid, r in emb.items() if r["own_rank"] > 1 and r["margin"] < -0.15}
flag_rows = [r for r in rows if r["summary_id"] in emb_flag]
ok_rows = [r for r in rows if r["summary_id"] not in emb_flag]

print("\n=== 结果(bge-reranker-v2-m3)===")
print(f"embedding判无关的 {len(flag_rows)} 条: ce_own 最大 = {max(r['ce_own'] for r in flag_rows):.4f}, "
      f"ce_margin 最大 = {max(r['ce_margin'] for r in flag_rows):+.4f}")
print(f"其余 {len(ok_rows)} 条:        ce_own 最小 = {min(r['ce_own'] for r in ok_rows):.4f}, "
      f"ce_margin 最小 = {min(r['ce_margin'] for r in ok_rows):+.4f}")
print("\n无关组明细:")
for r in sorted(flag_rows, key=lambda x: x["ce_margin"]):
    print(f"  {r['summary_id']}  ce_own={r['ce_own']:.4f}  ce_other={r['ce_other']:.4f}  margin={r['ce_margin']:+.4f}")
lo = sorted(ok_rows, key=lambda x: x["ce_own"])[:5]
print("\n正常组中 ce_own 最低的 5 条(检查是否有漏网/边界):")
for r in lo:
    print(f"  {r['summary_id']}  ce_own={r['ce_own']:.4f}  margin={r['ce_margin']:+.4f}")
