# -*- coding: utf-8 -*-
"""
Build dataset_viewer.html.

Principle: show data/ exactly as it is. Field names appear verbatim and
nothing derived, scored or flagged is added. Reading the five candidates
side by side inside their own article is what exposed the five populations.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "..", "..", "data")

articles = [json.loads(l) for l in
            open(os.path.join(DATA, "articles.jsonl"), encoding="utf-8")]
summaries = [json.loads(l) for l in
             open(os.path.join(DATA, "summaries.jsonl"), encoding="utf-8")]

by_article = {}
for s in summaries:
    by_article.setdefault(s["article_id"], []).append(s)

data = []
for a in articles:
    aid = a["article_id"]
    data.append({
        "article_id": aid,
        "url": a["url"],
        "title": a["title"],
        "text": a["text"],
        "reference_summary": a["reference_summary"],
        "summaries": [{"summary_id": s["summary_id"], "summary": s["summary"]}
                      for s in by_article.get(aid, [])],
    })

PAGE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dataset viewer &mdash; articles.jsonl / summaries.jsonl</title>
<style>
:root {
  --bg:#f6f7f9; --panel:#fff; --ink:#1a2233; --muted:#68748c; --line:#e3e7ee;
  --accent:#2456c8;
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
  font-family:-apple-system,"Hiragino Sans","Hiragino Kaku Gothic ProN","Noto Sans CJK JP",sans-serif;
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
#list { overflow-y:auto; flex:1; }
.item { padding:10px 16px; border-bottom:1px solid var(--line); cursor:pointer; }
.item:hover { background:#f0f4fb; }
.item.active { background:#e7eefc; border-left:3px solid var(--accent); padding-left:13px; }
.item .t { font-weight:600; font-size:13px; line-height:1.5; }
.item .m { font-size:11px; color:var(--muted); margin-top:3px; }
#main { flex:1; overflow-y:auto; padding:26px 34px 80px; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:20px 24px; margin-bottom:18px; max-width:1000px; }
h2 { margin:0 0 4px; font-size:19px; line-height:1.5; }
.meta { font-size:12px; color:var(--muted); margin-bottom:8px; }
.meta a { color:var(--accent); text-decoration:none; }
.field { font-size:12px; font-weight:700; letter-spacing:.05em; color:var(--muted);
  font-family:ui-monospace,Menlo,monospace; margin:16px 0 6px; }
.ja { white-space:pre-wrap; }
.sumcard { border:1px solid var(--line); border-radius:10px; padding:12px 16px; margin:10px 0; }
.sumhead { font-size:12px; color:var(--muted); margin-bottom:6px;
  font-family:ui-monospace,Menlo,monospace; }
#empty { color:var(--muted); margin-top:40vh; text-align:center; }
</style>
</head>
<body>
<div id="app">
  <div id="side">
    <header>
      <h1>Dataset viewer</h1>
      <div class="sub">articles.jsonl (50) &middot; summaries.jsonl (250)</div>
      <input id="search" placeholder="search title…">
    </header>
    <div id="list"></div>
  </div>
  <div id="main"><div id="empty">&larr; pick an article</div></div>
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
    if(q && !a.title.toLowerCase().includes(q)) return;
    const div=document.createElement("div");
    div.className="item"+(current===i?" active":"");
    div.innerHTML=`<div class="t">${esc(a.title)}</div>
      <div class="m">article_id: ${esc(a.article_id)}</div>`;
    div.onclick=()=>{ current=i; renderList(document.getElementById("search").value); renderMain(a); };
    listEl.appendChild(div);
  });
}
function renderMain(a){
  mainEl.innerHTML=`
  <div class="card">
    <h2>${esc(a.title)}</h2>
    <div class="meta">article_id: ${esc(a.article_id)} &middot; <a href="${esc(a.url)}" target="_blank">url &nearr;</a></div>
    <div class="field">reference_summary</div>
    <div class="ja">${esc(a.reference_summary)}</div>
    <div class="field">text</div>
    <div class="ja">${esc(a.text)}</div>
  </div>
  <div class="card">
    <div class="field" style="margin-top:0">summaries.jsonl records matching this article_id (${a.summaries.length})</div>
    ${a.summaries.map(s=>`
      <div class="sumcard">
        <div class="sumhead">summary_id: ${esc(s.summary_id)}</div>
        <div class="ja">${esc(s.summary)}</div>
      </div>`).join("")}
  </div>`;
  mainEl.scrollTop=0;
}
document.getElementById("search").addEventListener("input",e=>renderList(e.target.value));
renderList("");
</script>
</body>
</html>"""

out = PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
out_path = os.path.join(HERE, "dataset_viewer.html")
open(out_path, "w", encoding="utf-8").write(out)
print("OK -> %s  (%.2f MB)" % (out_path, len(out) / 1e6))
