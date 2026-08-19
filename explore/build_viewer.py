# -*- coding: utf-8 -*-
"""
生成数据集浏览器 dataset_viewer.html
读取 ../data/articles.jsonl / summaries.jsonl,
如存在 translations.json(中文翻译,可选)则一并嵌入。
自动检测标记(规则层雏形):抄参考 / 抄原文开头 / 疑似截断。
视图:文章视图(原文+5条摘要对照) / 总览视图(250条全量筛选表)。
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

articles = [json.loads(l) for l in open(os.path.join(DATA, "articles.jsonl"), encoding="utf-8")]
summaries = [json.loads(l) for l in open(os.path.join(DATA, "summaries.jsonl"), encoding="utf-8")]

trans_path = os.path.join(HERE, "translations.json")
translations = {}
if os.path.exists(trans_path):
    translations = json.load(open(trans_path, encoding="utf-8"))

SENT_END = tuple("。」!?!?')】》")

def flags(summary, article):
    t = summary.strip()
    ref = article["reference_summary"].strip()
    f = []
    if t == ref:
        f.append("ref_copy")
    elif ref.startswith(t) and len(t) < len(ref):
        f.append("ref_prefix")
    if "ref_copy" not in f and len(t) >= 40 and t[:40] in article["text"]:
        f.append("lead_copy")
    if not t.endswith(SENT_END):
        f.append("truncated")
    return f

def n_sent(t):
    return len([x for x in re.split(r"。", t) if x.strip()])

by_article = {}
for s in summaries:
    by_article.setdefault(s["article_id"], []).append(s)

data = []
flag_totals = {}
clean_count = 0
for a in articles:
    aid = a["article_id"]
    tr = translations.get(aid, {})
    subs = []
    for s in by_article.get(aid, []):
        fl = flags(s["summary"], a)
        for x in fl:
            flag_totals[x] = flag_totals.get(x, 0) + 1
        if not fl:
            clean_count += 1
        subs.append({
            "id": s["summary_id"],
            "text": s["summary"],
            "zh": tr.get("summaries", {}).get(s["summary_id"], ""),
            "flags": fl,
            "len": len(s["summary"]),
            "sents": n_sent(s["summary"]),
        })
    data.append({
        "id": aid,
        "url": a["url"],
        "title": a["title"],
        "title_zh": tr.get("title_zh", ""),
        "text": a["text"],
        "text_zh": tr.get("text_zh", ""),
        "ref": a["reference_summary"],
        "ref_zh": tr.get("ref_zh", ""),
        "len": len(a["text"]),
        "summaries": subs,
    })

PAGE = """<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>数据集浏览器 — 日语新闻摘要评估</title>
<style>
:root {
  --bg:#f6f7f9; --panel:#fff; --ink:#1a2233; --muted:#68748c; --line:#e3e7ee;
  --accent:#2456c8; --ja:#1a2233; --zh:#7a4d1f; --zhbg:#fdf6ec;
  --ref:#0b7a4b; --refbg:#edf9f2;
  --b-refcopy:#7c3aed; --b-lead:#c2410c; --b-trunc:#dc2626; --b-refpre:#9333ea; --b-clean:#94a3b8;
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
  font-family:-apple-system,"Hiragino Sans","Hiragino Kaku Gothic ProN","PingFang SC","Noto Sans CJK JP",sans-serif;
  font-size:14px; line-height:1.75; }
#app { display:flex; height:100vh; }
#side { width:330px; min-width:330px; border-right:1px solid var(--line); background:var(--panel);
  display:flex; flex-direction:column; }
#side header { padding:14px 16px 10px; border-bottom:1px solid var(--line); }
#side h1 { font-size:15px; margin:0 0 8px; }
#stats { font-size:12px; color:var(--muted); line-height:1.9; }
#stats b { color:var(--ink); }
#ovbtn { display:block; width:100%; margin-top:8px; padding:7px 10px; border:1px solid var(--accent);
  color:var(--accent); background:#fff; border-radius:8px; font-size:13px; font-weight:700; cursor:pointer; }
#ovbtn:hover, #ovbtn.active { background:var(--accent); color:#fff; }
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
.item .m { font-size:11px; color:var(--muted); margin-top:3px; display:flex; gap:6px; flex-wrap:wrap; }
#main { flex:1; overflow-y:auto; padding:26px 34px 80px; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:20px 24px; margin-bottom:18px; max-width:1100px; }
h2 { margin:0 0 4px; font-size:19px; line-height:1.5; }
.h2zh { color:var(--zh); font-size:15px; margin:2px 0 8px; display:none; }
body.zh .h2zh { display:block; }
.meta { font-size:12px; color:var(--muted); margin-bottom:14px; }
.meta a { color:var(--accent); text-decoration:none; }
.label { font-size:12px; font-weight:700; letter-spacing:.06em; color:var(--muted);
  text-transform:uppercase; margin:16px 0 6px; }
.ja { white-space:pre-wrap; }
.zhblk { white-space:pre-wrap; color:var(--zh); background:var(--zhbg);
  border-left:3px solid #e0b070; padding:8px 12px; border-radius:0 8px 8px 0;
  margin-top:8px; display:none; }
body.zh .zhblk { display:block; }
.refbox { background:var(--refbg); border:1px solid #bfe6d2; border-radius:8px; padding:10px 14px; }
.sumcard { border:1px solid var(--line); border-radius:10px; padding:12px 16px; margin:10px 0; }
.sumcard.hl { border-color:var(--accent); box-shadow:0 0 0 2px #c9d8f7; }
.sumhead { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:6px;
  font-size:12px; color:var(--muted); }
.sumhead code { background:#eef1f6; padding:1px 6px; border-radius:5px; font-size:11px; }
.badge { display:inline-block; padding:1px 8px; border-radius:20px; font-size:11px;
  font-weight:700; color:#fff; }
.b-ref_copy { background:var(--b-refcopy); } .b-ref_prefix { background:var(--b-refpre); }
.b-lead_copy { background:var(--b-lead); } .b-truncated { background:var(--b-trunc); }
.b-clean { background:var(--b-clean); }
#empty { color:var(--muted); margin-top:40vh; text-align:center; }
/* 总览 */
.chips { display:flex; gap:8px; flex-wrap:wrap; margin:10px 0 14px; }
.chip { padding:4px 12px; border-radius:20px; border:1px solid var(--line); background:#fff;
  font-size:12px; font-weight:600; cursor:pointer; color:var(--muted); }
.chip.on { color:#fff; border-color:transparent; }
.chip.on.c-all { background:var(--accent); } .chip.on.c-clean { background:var(--b-clean); }
.chip.on.c-ref_copy { background:var(--b-refcopy); } .chip.on.c-ref_prefix { background:var(--b-refpre); }
.chip.on.c-lead_copy { background:var(--b-lead); } .chip.on.c-truncated { background:var(--b-trunc); }
.bars { margin:6px 0 4px; max-width:560px; }
.bar { display:flex; align-items:center; gap:10px; font-size:12px; margin:4px 0; }
.bar .nm { width:110px; color:var(--muted); text-align:right; }
.bar .tk { height:14px; border-radius:4px; min-width:2px; }
.bar .ct { color:var(--ink); font-weight:700; }
.tblwrap { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:13px; }
th { text-align:left; font-size:11px; color:var(--muted); text-transform:uppercase;
  letter-spacing:.05em; padding:6px 10px; border-bottom:2px solid var(--line); white-space:nowrap; }
td { padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }
tr.row { cursor:pointer; } tr.row:hover { background:#f0f4fb; }
td .snip { line-height:1.6; }
td .snipzh { color:var(--zh); font-size:12px; display:none; }
body.zh td .snipzh { display:block; }
td .art { font-size:11px; color:var(--muted); white-space:nowrap; max-width:180px;
  overflow:hidden; text-overflow:ellipsis; }
.num { text-align:right; white-space:nowrap; color:var(--muted); }
</style>
</head>
<body>
<div id="app">
  <div id="side">
    <header>
      <h1>📰 数据集浏览器 <span style="color:var(--muted);font-weight:400">50 篇 / 250 摘要</span></h1>
      <div id="stats">__STATS__</div>
      <button id="ovbtn">📊 全部 250 条总览</button>
      <input id="search" placeholder="搜索标题(日/中)…">
      <label id="zhtoggle"><input type="checkbox" id="zhcb"> 显示中文翻译</label>
    </header>
    <div id="list"></div>
  </div>
  <div id="main"><div id="empty">← 选择文章,或点击"全部 250 条总览"</div></div>
</div>
<script>
const DATA = __DATA__;
const FLAG_NAME = { ref_copy:"抄参考摘要", ref_prefix:"参考摘要截断版", lead_copy:"照抄原文开头", truncated:"疑似截断", clean:"无标记" };
const FLAG_COLOR = { ref_copy:"var(--b-refcopy)", ref_prefix:"var(--b-refpre)", lead_copy:"var(--b-lead)", truncated:"var(--b-trunc)", clean:"var(--b-clean)" };
const listEl = document.getElementById("list");
const mainEl = document.getElementById("main");
let current = null, ovFilter = "all";

const ALL = [];
DATA.forEach((a,ai)=>a.summaries.forEach((s,si)=>ALL.push({a,ai,s,si})));

function esc(s){ const d=document.createElement("div"); d.textContent=s; return d.innerHTML; }
function badges(fl){
  if(!fl.length) return '<span class="badge b-clean">无标记</span>';
  return fl.map(f=>`<span class="badge b-${f}">${FLAG_NAME[f]||f}</span>`).join(" ");
}
function renderList(q){
  q=(q||"").toLowerCase();
  listEl.innerHTML="";
  DATA.forEach((a,i)=>{
    if(q && !(a.title.toLowerCase().includes(q)||(a.title_zh||"").toLowerCase().includes(q))) return;
    const allFlags=[...new Set(a.summaries.flatMap(s=>s.flags))];
    const div=document.createElement("div");
    div.className="item"+(current===i?" active":"");
    div.innerHTML=`<div class="t">${esc(a.title)}</div>
      <div class="tz">${esc(a.title_zh||"")}</div>
      <div class="m"><span>#${esc(a.id)}</span><span>${a.len}字</span>${badges(allFlags)}</div>`;
    div.onclick=()=>{ current=i; setOv(false); renderList(document.getElementById("search").value); renderMain(a); };
    listEl.appendChild(div);
  });
}
function zhblk(t){ return t?`<div class="zhblk">${esc(t)}</div>`:""; }
function renderMain(a, hlId){
  mainEl.innerHTML=`
  <div class="card">
    <h2>${esc(a.title)}</h2>
    <div class="h2zh">${esc(a.title_zh||"")}</div>
    <div class="meta">#${esc(a.id)} · ${a.len} 字 · <a href="${esc(a.url)}" target="_blank">BBC 原文 ↗</a></div>
    <div class="label">参考摘要(XL-Sum,质量不均,仅作参照)</div>
    <div class="refbox"><div class="ja">${esc(a.ref)}</div>${zhblk(a.ref_zh)}</div>
    <div class="label">文章全文</div>
    <div class="ja">${esc(a.text)}</div>
    ${zhblk(a.text_zh)}
  </div>
  <div class="card">
    <div class="label" style="margin-top:0">该文章的 5 条待评摘要</div>
    ${a.summaries.map((s,i)=>`
      <div class="sumcard${s.id===hlId?" hl":""}" id="sc-${esc(s.id)}">
        <div class="sumhead"><b>摘要 ${i+1}</b> <code>${esc(s.id)}</code>
          <span>${s.len}字 · ${s.sents}句</span> ${badges(s.flags)}</div>
        <div class="ja">${esc(s.text)}</div>
        ${zhblk(s.zh)}
      </div>`).join("")}
  </div>`;
  mainEl.scrollTop=0;
  if(hlId){ const el=document.getElementById("sc-"+hlId); if(el) el.scrollIntoView({block:"center"}); }
}
function counts(){
  const c={all:ALL.length, clean:0, ref_copy:0, ref_prefix:0, lead_copy:0, truncated:0};
  ALL.forEach(r=>{ if(!r.s.flags.length) c.clean++; r.s.flags.forEach(f=>c[f]++); });
  return c;
}
function renderOverview(){
  const c=counts();
  const keys=["ref_copy","ref_prefix","lead_copy","truncated","clean"];
  const maxc=Math.max(...keys.map(k=>c[k]));
  const rows=ALL.filter(r=> ovFilter==="all" ? true : (ovFilter==="clean" ? !r.s.flags.length : r.s.flags.includes(ovFilter)));
  mainEl.innerHTML=`
  <div class="card">
    <h2>全部 250 条摘要总览</h2>
    <div class="meta">自动检测标记为规则层雏形结果;"无标记"不代表没问题——幻觉、事实反转、跑题都藏在里面,需人工/语义层判断。</div>
    <div class="bars">${keys.map(k=>`
      <div class="bar"><span class="nm">${FLAG_NAME[k]}</span>
        <span class="tk" style="width:${Math.round(c[k]/maxc*320)}px;background:${FLAG_COLOR[k]}"></span>
        <span class="ct">${c[k]}</span></div>`).join("")}
    </div>
    <div class="chips">
      ${["all",...keys].map(k=>`<span class="chip c-${k} ${ovFilter===k?"on":""}" data-f="${k}">
        ${k==="all"?"全部":FLAG_NAME[k]} (${c[k]})</span>`).join("")}
    </div>
    <div class="tblwrap"><table>
      <tr><th>#</th><th>文章</th><th>摘要</th><th>标记</th><th>字数</th><th>句数</th></tr>
      ${rows.map((r,i)=>`
        <tr class="row" data-ai="${r.ai}" data-sid="${esc(r.s.id)}">
          <td class="num">${i+1}</td>
          <td><div class="art" title="${esc(r.a.title)}">${esc(r.a.title)}</div>
              <div class="art" style="color:#9aa4b8">#${esc(r.a.id)}</div></td>
          <td><div class="snip ja">${esc(r.s.text.slice(0,90))}${r.s.text.length>90?"…":""}</div>
              <div class="snipzh">${esc((r.s.zh||"").slice(0,90))}${(r.s.zh||"").length>90?"…":""}</div></td>
          <td>${badges(r.s.flags)}</td>
          <td class="num">${r.s.len}</td><td class="num">${r.s.sents}</td>
        </tr>`).join("")}
    </table></div>
  </div>`;
  mainEl.scrollTop=0;
  mainEl.querySelectorAll(".chip").forEach(ch=>ch.onclick=()=>{ ovFilter=ch.dataset.f; renderOverview(); });
  mainEl.querySelectorAll("tr.row").forEach(tr=>tr.onclick=()=>{
    current=+tr.dataset.ai; setOv(false); renderList(document.getElementById("search").value);
    renderMain(DATA[current], tr.dataset.sid);
  });
}
function setOv(on){ document.getElementById("ovbtn").classList.toggle("active",on); if(on){ current=null; renderList(""); } }
document.getElementById("ovbtn").onclick=()=>{ setOv(true); renderOverview(); };
document.getElementById("search").addEventListener("input",e=>renderList(e.target.value));
document.getElementById("zhcb").addEventListener("change",e=>{
  document.body.classList.toggle("zh",e.target.checked);
});
renderList("");
</script>
</body>
</html>"""

stats_parts = []
name = {"ref_copy": "抄参考", "ref_prefix": "参考截断版", "lead_copy": "抄原文开头", "truncated": "疑似截断"}
for k in ["ref_copy", "ref_prefix", "lead_copy", "truncated"]:
    if k in flag_totals:
        stats_parts.append(f"{name[k]} <b>{flag_totals[k]}</b>")
stats_parts.append(f"无标记 <b>{clean_count}</b>")
stats_html = "自动标记:" + " · ".join(stats_parts)

out = PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False)).replace("__STATS__", stats_html)
out_path = os.path.join(HERE, "dataset_viewer.html")
open(out_path, "w", encoding="utf-8").write(out)
print(f"OK -> {out_path}  ({len(out)/1e6:.2f} MB, 翻译覆盖 {len(translations)}/50 篇, 无标记 {clean_count}/250)")
