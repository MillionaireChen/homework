import json, collections
codex={json.loads(l)['summary_id']:json.loads(l) for l in open('evaluation_runs_GPT/full250_codex/score.jsonl',encoding='utf-8')}
rows=json.load(open('ref_hit_rows.json',encoding='utf-8'))
cat={r['sid']:r['cat'] for r in rows}
byart=collections.defaultdict(list)
for r in rows: byart[r['aid']].append(r['sid'])
pos=collections.Counter(); beaten=[]
for a,ids in byart.items():
    ranked=sorted(ids,key=lambda i:-codex[i]['score'])
    refs=[i for i in ids if cat[i]=='EXACT']
    best=min(ranked.index(i) for i in refs)+1
    pos[best]+=1
    if best>1:
        w=ranked[0]
        beaten.append((a,codex[w]['score'],cat[w],max(codex[i]['score'] for i in refs)))
print('=== within-article rank of the reference-verbatim candidate (by codex score, 1=top of 5) ===')
for k in sorted(pos): print(f'  rank {k}: {pos[k]} articles')
print(f'  reference ranked #1 in {pos[1]}/50 articles ({pos[1]/50*100:.0f}%)')
print('\n=== articles where a non-reference candidate outscored the reference ===')
for a,s,c,rs in sorted(beaten,key=lambda x:-(x[1]-x[3])):
    print(f'  {a:34s} winner={s} ({c})  reference={rs}  gap=+{s-rs}')
