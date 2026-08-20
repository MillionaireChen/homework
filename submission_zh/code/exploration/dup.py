import json, collections
codex={json.loads(l)['summary_id']:json.loads(l) for l in open('evaluation_runs_GPT/full250_codex/score.jsonl',encoding='utf-8')}
rows=json.load(open('ref_hit_rows.json',encoding='utf-8'))
per=collections.defaultdict(list)
for r in rows:
    if r['cat']=='EXACT': per[r['aid']].append(r['sid'])
print('=== duplicate reference-verbatim pairs (identical text, scored twice) ===')
same=0
for a,ids in sorted(per.items()):
    if len(ids)<2: continue
    d=[(i,codex[i]['score'],codex[i]['quality_label'],codex[i]['dimensions']) for i in ids]
    ok = len({(x[1],tuple(sorted(x[3].items()))) for x in d})==1
    same += ok
    print(f'  {a:12s} ' + ' | '.join(f'{i.split("_")[-1]}={s}/{l}' for i,s,l,_ in d) + ('   IDENTICAL' if ok else '   *** DIVERGED'))
print(f'  -> {same}/{len(( [a for a,i in per.items() if len(i)>1]))} pairs scored identically on score AND all four dimensions')
