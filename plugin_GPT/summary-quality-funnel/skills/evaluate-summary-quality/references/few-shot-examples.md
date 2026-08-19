# Few-shot example bank

Use synthetic examples only. Inject the smallest matching example into each Agent call. Do not include the entire bank.

## ANCHOR_GENERATION

Input article:

```text
市は10日、豪雨で損傷した中央橋を12日から通行止めにすると発表した。復旧には約2週間かかる見通しで、市は東橋への迂回を呼びかけている。人的被害は確認されていない。
```

Expected anchor:

```json
{"main_event":"豪雨で損傷した中央橋が12日から通行止めになる","key_facts":["市が10日に発表","復旧見通しは約2週間","東橋への迂回を要請","人的被害なし"],"anchor_summary":"市は、豪雨で損傷した中央橋を12日から通行止めにすると発表した。復旧には約2週間かかる見通しで、東橋への迂回を呼びかけている。"}
```

## EMPTY

```json
{"article":"市は新図書館を開館した。","summary":"   ","draft_terminal_result":"EMPTY_OUTPUT","expected_review":"APPROVE","expected_score":0,"terminal_rank":0}
```

## OVER_LENGTH

Article: `市は新図書館を開館した。蔵書は20万冊。子ども向け区画も設けた。`

Candidate: `市は新図書館を開館した。蔵書は20万冊ある。子ども向け区画を設けた。開館時間は午前9時からだ。`

Expected:

```json
{"draft_terminal_result":"OVER_SENTENCE_LIMIT","sentence_count":4,"expected_review":"APPROVE","expected_score":0,"terminal_rank":3}
```

## COPY

Article: `市は10日、豪雨で損傷した中央橋を12日から通行止めにすると発表した。復旧には約2週間かかる見通しだ。`

Candidate: `市は10日、豪雨で損傷した中央橋を12日から通行止めにすると発表した。復旧には約2週間かかる見通しだ。`

Expected:

```json
{"draft_terminal_result":"VERBATIM_SOURCE_COPY","full_containment":true,"expected_review":"APPROVE","expected_score":0,"terminal_rank":1}
```

## TRUNCATED

Article: `政府は新制度を4月から始めると発表した。対象は全国の中小企業である。`

Candidate: `政府は新制度を4月から始めると発表したが、`

Expected:

```json
{"draft_terminal_result":"OBVIOUS_TRUNCATION","final_character":"、","expected_review":"APPROVE","expected_score":0,"terminal_rank":2}
```

## OFF_TOPIC

Article: `北海道で大雪となり、鉄道各社は計50本を運休した。`

Candidate: `中央銀行は政策金利を0.25ポイント引き上げた。`

Expected:

```json
{"draft_terminal_result":"OFF_TOPIC","expected_review":"APPROVE","expected_score":0,"terminal_rank":0,"reason":"主体・事件・領域がすべて原文と無関係"}
```

## REVIEW_REJECT_BORDERLINE

Article: `首相は「支援を続ける」と述べた。政府は来月、追加策を公表する。`

Candidate: `首相は支援継続を表明し、政府は来月追加策を公表する。`

Draft: `VERBATIM_SOURCE_COPY`

Expected review:

```json
{"decision":"REJECT","reason":"事実上の言い換えであり、全文の連続コピーではない","continue_at":"relevance_check"}
```

## EXCELLENT

Article: `市は豪雨で損傷した中央橋を12日から通行止めにする。復旧は約2週間の見通しで、人的被害はない。`

Candidate: `市は、豪雨で損傷した中央橋を12日から通行止めにすると発表した。復旧には約2週間かかる見通しで、人的被害は確認されていない。`

Expected draft:

```json
{"dimensions":{"faithfulness":50,"coverage":29,"coherence":15,"conciseness":5},"score":99,"quality_label":"EXCELLENT"}
```

## FACTUAL_ERROR

Article: `列車事故で10人が軽傷を負った。死者はいない。`

Candidate: `列車事故で10人が死亡した。`

Expected draft:

```json
{"claim_checks":[{"claim":"10人が死亡した","verdict":"CONTRADICTED","source_evidence":"10人が軽傷を負った。死者はいない"}],"dimensions":{"faithfulness":0,"coverage":12,"coherence":13,"conciseness":5},"score":30,"quality_label":"POOR"}
```

## LOW_COVERAGE

Article: `政府は大型減税案を可決した。対象は約500万世帯で、来年1月に始まる。野党は財源不足を批判した。`

Candidate: `野党は政府を批判した。`

Expected draft:

```json
{"dimensions":{"faithfulness":50,"coverage":5,"coherence":13,"conciseness":5},"score":73,"quality_label":"MIXED","issues":["減税案の可決、対象、開始時期を欠く"]}
```

## INCOHERENT

Article: `チームは決勝で3対1で勝利し、初優勝した。監督は選手を称賛した。`

Candidate: `監督が称賛した。初優勝は3対1で、選手は決勝だった。`

Expected draft:

```json
{"dimensions":{"faithfulness":35,"coverage":18,"coherence":3,"conciseness":4},"score":60,"quality_label":"MIXED","issues":["語順と係り受けが崩れ、出来事の関係が不明瞭"]}
```

## VERBOSE

Article: `大学は来春、新しい工学部を開設する。定員は200人。`

Candidate: `大学は来春、新しい工学部を開設する予定だ。新しい学部は工学部であり、定員については200人という人数が設定されている。`

Expected draft:

```json
{"dimensions":{"faithfulness":50,"coverage":30,"coherence":13,"conciseness":1},"score":94,"quality_label":"EXCELLENT","issues":["重複表現があり簡潔性を欠く"]}
```

## REVIEW_APPROVE

Scorer draft: `score=73`, with supported claims and a documented main-event omission.

Expected review:

```json
{"decision":"APPROVE","confidence":"HIGH","findings":[]}
```

## REVIEW_REVISE

Article says `死者はいない`; candidate says `10人が死亡`; Scorer marks the claim `SUPPORTED` and gives faithfulness `45/50`.

Expected review:

```json
{"decision":"REVISE","confidence":"HIGH","findings":["死亡 claim 与原文矛盾"],"suggested_dimensions":{"faithfulness":0,"coverage":12,"coherence":13,"conciseness":5}}
```

## REPORT_SUMMARY

Audited statistics:

```json
{"input":{"pairs":10,"unique_articles":5,"reference_summary_used":false},"funnel":{"fully_soft_scored":7,"terminal_total":3,"terminal_by_type":{"VERBATIM_SOURCE_COPY":2,"OFF_TOPIC":1}},"soft_scores":{"mean":81.4,"minimum":62,"maximum":97,"labels":{"EXCELLENT":2,"GOOD":3,"MIXED":2}},"review":{"approved":10,"revised_at_least_once":1}}
```

Expected style:

```markdown
## 1. 输入数据

本次从5篇文章抽取10组文章—摘要对；运行时未使用参考摘要。

## 2. 漏斗过程

7组进入完整软评分，3组提前终止：2组原文复制、1组完全无关。

![流程结果](report_assets/pipeline_outcomes.png)

## 3. 统计结果

软评分平均81.4分，范围62–97；2组EXCELLENT、3组GOOD、2组MIXED。Reviewer复核全部10组，并修订1组。

![软评分](report_assets/soft_score_results.png)

## 4. 结论

本轮支持“可用原型，需要扩大验证”：漏斗能拦截明确违规并产生可审计评分，但样本量不足以证明生产稳定性。
```
