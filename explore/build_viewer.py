# -*- coding: utf-8 -*-
"""
生成数据集浏览器 dataset_viewer.html
原则:如实展示 data/ 原始数据,字段名原样显示,不添加任何派生标记或判断。
唯一的附加内容:中文翻译(translations.json,存在则插入对应字段下方)。
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

articles = [json.loads(l) for l in open(os.path.join(DATA, "articles.jsonl"), encoding="utf-8")]
summaries = [json.loads(l) for l in open(os.path.join(DATA, "summaries.jsonl"), encoding="utf-8")]

trans_path = os.path.join(HERE, "translations.json")
translations = {}
if os.path.exists(trans_path):
    translations = json.load(open(trans_path, encoding="utf-8"))

by_article = {}
for s in summaries:
    by_article.setdefault(s["article_id"], []).append(s)

data = []
for a in articles:
    aid = a["article_id"]
    tr = translations.get(aid, {})
    subs = []
    for s in by_article.get(aid, []):
        subs.append({
            "summary_id": s["summary_id"],
            "summary": s["summary"],
            "zh": tr.get("summaries", {}).get(s["summary_id"], ""),
        })
    data.append({
        "article_id": aid,
        "url": a["url"],
        "title": a["title"],
        "title_zh": tr.get("title_zh", ""),
        "text": a["text"],
        "text_zh": tr.get("text_zh", ""),
        "reference_summary": a["reference_summary"],
        "ref_zh": tr.get("ref_zh", ""),
        "summaries": subs,
    })

PAGE = """<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>数据集浏览器 — articles.jsonl / summaries.jsonl</title>
<style>
:root {
  --bg:#f6f7f9; --panel:#fff; --ink:#1a2233; --muted:#68748c; --line:#e3e7ee;
  --accent:#2456c8; --zh:#7a4d1f; --zhbg:#fdf6ec;
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
  font-family:-apple-system,"Hiragino Sans","Hiragino Kaku Gothic ProN","PingFang SC","Noto Sans CJK JP",sans-serif;
  font-size:14px; line-height:1.75; }
#app { display:flex; height:100vh; }
#side { width:330px; min-width:330px; border-right:1px solid var(--line); background:var(--panel);
  display:flex; flex-direction:column; }
#side header { padding:14px 16px 10px; border-bottom:1px solid var(--line); }
#side h1 { font-size:15px; margin:0 0 4px; }
#side .sub { font-size:12px; color:var(--muted); }
#search { width:100%; padding:7px 10px; border:1px solid var(--line); border-radius:8px;
  font-size:13px; margin-top:8px; outline:none; }
#search:focus { border-color:var(--accent); }
#zhtoggle { display:flex; align-items:center; gap:6px; margin-top:8px; font-size:13px;
  cursor:pointer; user-select:none; color:var(--zh); font-weight:600; }
#list { overflow-y:auto; flex:1; }
.item { padding:10px 16px; border-bottom:1px solid var(--line); cursor:pointer; }
.item:hover { background:#f0f4fb; }
.item.active { background:#e7eefc; border-left:3px solid var(--accent); padding-left:13px; }
.item .t { font-weight:600; font-size:13px; line-height:1.5; }
.item .tz { font-size:12px; color:var(--zh); line-height:1.5; display:none; }
body.zh .item .tz { display:block; }
.item .m { font-size:11px; color:var(--muted); margin-top:3px; }
#main { flex:1; overflow-y:auto; padding:26px 34px 80px; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:20px 24px; margin-bottom:18px; max-width:1000px; }
h2 { margin:0 0 4px; font-size:19px; line-height:1.5; }
.h2zh { color:var(--zh); font-size:15px; margin:2px 0 8px; display:none; }
body.zh .h2zh { display:block; }
.meta { font-size:12px; color:var(--muted); margin-bottom:8px; }
.meta a { color:var(--accent); text-decoration:none; }
.field { font-size:12px; font-weight:700; letter-spacing:.05em; color:var(--muted);
  font-family:ui-monospace,Menlo,monospace; margin:16px 0 6px; }
.ja { white-space:pre-wrap; }
.zhblk { white-space:pre-wrap; color:var(--zh); background:var(--zhbg);
  border-left:3px solid #e0b070; padding:8px 12px; border-radius:0 8px 8px 0;
  margin-top:8px; display:none; }
body.zh .zhblk { display:block; }
.sumcard { border:1px solid var(--line); border-radius:10px; padding:12px 16px; margin:10px 0; }
.sumhead { font-size:12px; color:var(--muted); margin-bottom:6px;
  font-family:ui-monospace,Menlo,monospace; }
#empty { color:var(--muted); margin-top:40vh; text-align:center; }
</style>
</head>
<body class="zh">
<div id="app">
  <div id="side">
    <header>
      <h1>数据集浏览器</h1>
      <div class="sub">articles.jsonl(50)· summaries.jsonl(250)</div>
      <input id="search" placeholder="搜索 title(日/中)…">
      <label id="zhtoggle"><input type="checkbox" id="zhcb" checked> 显示中文翻译</label>
    </header>
    <div id="list"></div>
  </div>
  <div id="main"><div id="empty">← 从左侧选择一篇文章</div></div>
</div>
<script>
const DATA = __DATA__;
const listEl = document.getElementById("list");
const mainEl = document.getElementById("main");
let current = null;

function esc(s){ const d=document.createElement("div"); d.textContent=s; return d.innerHTML; }
function renderList(q){
  q=(q||"").toLowerCase();
  listEl.innerHTML="";
  DATA.forEach((a,i)=>{
    if(q && !(a.title.toLowerCase().includes(q)||(a.title_zh||"").toLowerCase().includes(q))) return;
    const div=document.createElement("div");
    div.className="item"+(current===i?" active":"");
    div.innerHTML=`<div class="t">${esc(a.title)}</div>
      <div class="tz">${esc(a.title_zh||"")}</div>
      <div class="m">article_id: ${esc(a.article_id)}</div>`;
    div.onclick=()=>{ current=i; renderList(document.getElementById("search").value); renderMain(a); };
    listEl.appendChild(div);
  });
}
function zhblk(t){ return t?`<div class="zhblk">${esc(t)}</div>`:""; }
function renderMain(a){
  mainEl.innerHTML=`
  <div class="card">
    <h2>${esc(a.title)}</h2>
    <div class="h2zh">${esc(a.title_zh||"")}</div>
    <div class="meta">article_id: ${esc(a.article_id)} · <a href="${esc(a.url)}" target="_blank">url ↗</a></div>
    <div class="field">reference_summary</div>
    <div class="ja">${esc(a.reference_summary)}</div>
    ${zhblk(a.ref_zh)}
    <div class="field">text</div>
    <div class="ja">${esc(a.text)}</div>
    ${zhblk(a.text_zh)}
  </div>
  <div class="card">
    <div class="field" style="margin-top:0">summaries.jsonl 中 article_id 匹配的记录(${a.summaries.length} 条)</div>
    ${a.summaries.map(s=>`
      <div class="sumcard">
        <div class="sumhead">summary_id: ${esc(s.summary_id)}</div>
        <div class="ja">${esc(s.summary)}</div>
        ${zhblk(s.zh)}
      </div>`).join("")}
  </div>`;
  mainEl.scrollTop=0;
}
document.getElementById("search").addEventListener("input",e=>renderList(e.target.value));
document.getElementById("zhcb").addEventListener("change",e=>{
  document.body.classList.toggle("zh",e.target.checked);
});
renderList("");
</script>
</body>
</html>"""

out = PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
out_path = os.path.join(HERE, "dataset_viewer.html")
open(out_path, "w", encoding="utf-8").write(out)
print(f"OK -> {out_path}  ({len(out)/1e6:.2f} MB, 翻译覆盖 {len(translations)}/50 篇)")
