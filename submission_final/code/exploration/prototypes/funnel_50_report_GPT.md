# 50-summary funnel probe (GPT)

This is a small, reference-free test. `reference_summary` was not read or used.

## Outcome

- Tested summaries: 50
- `COPY_REJECT`: 10
- `OFFTOPIC_REJECT`: 3
- `PASS_TO_SEMANTIC`: 37

## Rejected summaries

| decision | summary_id | assigned article | strongest matched article | evidence |
|---|---|---|---|---|
| OFFTOPIC_REJECT | `35647760_cfdbf473` | オバマ氏、グアンタナモ収容所の閉鎖計画を発表 | 米ニューヨーク市の医師が自殺 新型ウイルスの最前線で勤務 | emb rank=14, margin=-0.383; rerank margin=-1.000 |
| COPY_REJECT | `35647760_e293a04b` | オバマ氏、グアンタナモ収容所の閉鎖計画を発表 | — | full=True; longest=157 chars; shingle12=1.000 |
| COPY_REJECT | `38476572_7d88f5af` | シリア停戦合意、ほぼ持続 国連安保理は投票へ | — | full=True; longest=240 chars; shingle12=1.000 |
| COPY_REJECT | `39776572_9264a945` | 米人気コメディアン、息子が九死に一生を得たと | — | full=True; longest=177 chars; shingle12=1.000 |
| COPY_REJECT | `45583472_014b86bd` | 実はヨーグルト製品には砂糖がいっぱい（オーガニックでも） コーラよりも | — | full=True; longest=169 chars; shingle12=1.000 |
| COPY_REJECT | `46669858_c2275577` | インドネシア津波で人気バンド流される 生存メンバーが涙の報告 | — | full=True; longest=181 chars; shingle12=1.000 |
| OFFTOPIC_REJECT | `48493511_28905ea8` | 天安門事件の鎮圧は「正しい」と中国国防相 30周年を前に異例の言及 | シリア停戦合意、ほぼ持続 国連安保理は投票へ | emb rank=3, margin=-0.211; rerank margin=-0.989 |
| COPY_REJECT | `48493511_abe69178` | 天安門事件の鎮圧は「正しい」と中国国防相 30周年を前に異例の言及 | — | full=True; longest=142 chars; shingle12=1.000 |
| COPY_REJECT | `50469832_512cbe90` | イスラエル入植地「違法ではない」 米政府が方針転換 | — | full=True; longest=261 chars; shingle12=1.000 |
| COPY_REJECT | `53274336_cbcf19e0` | 韓国のトライアスロン選手が自殺、コーチらが長年暴力か | — | full=True; longest=169 chars; shingle12=1.000 |
| COPY_REJECT | `55155049_2d012498` | 【米大統領選2020】 バー司法長官、大規模な不正は「確認できていない」 | — | full=True; longest=244 chars; shingle12=1.000 |
| OFFTOPIC_REJECT | `55155049_bbe6c482` | 【米大統領選2020】 バー司法長官、大規模な不正は「確認できていない」 | 記者を「国民の敵」と呼ぶべきでない NYタイムズ社主、トランプ氏に | emb rank=4, margin=-0.293; rerank margin=-0.999 |
| COPY_REJECT | `features-and-analysis-46478194_67a2365c` | いじめた罰だ、学校まで歩きなさい――父親のしつけビデオで議論 | — | full=True; longest=166 chars; shingle12=1.000 |

## Interpretation

This funnel only removes obvious failures. A passed summary is not automatically good; it still needs faithfulness, coverage, completeness, and fluency evaluation.
