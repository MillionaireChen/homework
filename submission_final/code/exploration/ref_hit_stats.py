import json, unicodedata, re, collections
from difflib import SequenceMatcher

def norm(s):
    s = unicodedata.normalize('NFKC', s or '')
    s = re.sub(r'\s+', '', s)
    return s

arts = {}
for l in open('data/articles.jsonl', encoding='utf-8'):
    d = json.loads(l); arts[d['article_id']] = d
sums = [json.loads(l) for l in open('data/summaries.jsonl', encoding='utf-8')]
codex = {}
for l in open('evaluation_runs_GPT/full250_codex/score.jsonl', encoding='utf-8'):
    d = json.loads(l); codex[d['summary_id']] = d

rows = []
for s in sums:
    art = arts[s['article_id']]
    c, r = norm(s['summary']), norm(art['reference_summary'])
    ratio = SequenceMatcher(None, c, r).ratio() if c and r else 0.0
    if c == r:
        cat = 'EXACT'
    elif c and r.startswith(c):
        cat = 'REF_PREFIX'          # candidate = truncated reference
    elif c and r and c in r:
        cat = 'REF_SUBSTRING'
    elif r and c and r in c:
        cat = 'REF_PLUS_EXTRA'      # reference fully inside a longer candidate
    elif ratio >= 0.90:
        cat = 'NEAR_0.90+'
    elif ratio >= 0.70:
        cat = 'NEAR_0.70-0.90'
    else:
        cat = 'UNRELATED_TO_REF'
    cx = codex.get(s['summary_id'], {})
    rows.append(dict(sid=s['summary_id'], aid=s['article_id'], cat=cat, ratio=round(ratio, 4),
                     clen=len(c), rlen=len(r),
                     score=cx.get('score'), label=cx.get('quality_label'),
                     terminal=cx.get('terminal_result')))

print('=== 1. reference-hit categories over all 250 ===')
for k, v in collections.Counter(r['cat'] for r in rows).most_common():
    print(f'{k:18s} {v:4d}  ({v/250*100:.1f}%)')

hit = [r for r in rows if r['cat'] in ('EXACT','REF_PREFIX','REF_SUBSTRING','REF_PLUS_EXTRA','NEAR_0.90+')]
print(f'\nstrict hit (exact/prefix/substring/superset/near>=0.90): {len(hit)} / 250')

print('\n=== 2. per-article count of exact reference matches ===')
per = collections.Counter(r['aid'] for r in rows if r['cat'] == 'EXACT')
dist = collections.Counter(per.get(a, 0) for a in arts)
for k in sorted(dist):
    print(f'  articles with {k} exact ref-match among their 5 candidates: {dist[k]}')
print('  articles with >=2 exact:', sorted(a for a, n in per.items() if n >= 2))
print('  articles with 0 exact:', sorted(a for a in arts if per.get(a, 0) == 0))

print('\n=== 3. codex outcome x reference-hit category ===')
tab = collections.defaultdict(collections.Counter)
for r in rows:
    key = r['terminal'] or r['label']
    tab[r['cat']][key] += 1
for cat in ('EXACT','REF_PREFIX','REF_SUBSTRING','REF_PLUS_EXTRA','NEAR_0.90+','NEAR_0.70-0.90','UNRELATED_TO_REF'):
    if cat not in tab: continue
    tot = sum(tab[cat].values())
    print(f'\n{cat} (n={tot})')
    for k, v in tab[cat].most_common():
        print(f'   {str(k):24s} {v:4d}')
    sc = [r['score'] for r in rows if r['cat'] == cat and r['score'] and r['score'] > 0]
    if sc:
        sc.sort()
        print(f'   soft-scored n={len(sc)} mean={sum(sc)/len(sc):.2f} median={sc[len(sc)//2]} range={sc[0]}-{sc[-1]}')

print('\n=== 4. exact ref-matches that codex did NOT score EXCELLENT ===')
for r in sorted((r for r in rows if r['cat']=='EXACT'), key=lambda x: (x['score'] is None, x['score'])):
    if r['label'] != 'EXCELLENT':
        print(f"   {r['sid']:42s} score={str(r['score']):>4s} {r['label']} {r['terminal'] or ''}")

print('\n=== 5. length check on REF_PREFIX / truncated-reference cases ===')
for r in rows:
    if r['cat'] in ('REF_PREFIX','REF_SUBSTRING'):
        print(f"   {r['sid']:42s} cand={r['clen']:4d}ch ref={r['rlen']:4d}ch ratio={r['ratio']} -> {r['terminal'] or r['label']}")

json.dump(rows, open('ref_hit_rows.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
