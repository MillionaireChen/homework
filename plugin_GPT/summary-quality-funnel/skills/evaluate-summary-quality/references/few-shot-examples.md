# Few-shot example bank

Use synthetic examples only. Inject the smallest matching example into each Agent call. Do not include the entire bank.

The Japanese passages below are evaluation inputs and source-evidence fixtures, not project documentation. Explanations, labels, and control fields remain English.

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
{"draft_terminal_result":"OFF_TOPIC","expected_review":"APPROVE","expected_score":0,"terminal_rank":0,"reason":"The subject, event, and domain are all unrelated to the article."}
```

## REVIEW_REJECT_BORDERLINE

Article: `首相は「支援を続ける」と述べた。政府は来月、追加策を公表する。`

Candidate: `首相は支援継続を表明し、政府は来月追加策を公表する。`

Draft: `VERBATIM_SOURCE_COPY`

Expected review:

```json
{"decision":"REJECT","reason":"This is a substantive paraphrase, not a continuous full-candidate copy.","continue_at":"relevance_check"}
```

## EXCELLENT

Article: `市は豪雨で損傷した中央橋を12日から通行止めにする。復旧は約2週間の見通しで、人的被害はない。`

Candidate: `市は、豪雨で損傷した中央橋を12日から通行止めにすると発表した。復旧には約2週間かかる見通しで、人的被害は確認されていない。`

Expected draft:

```json
{"dimensions":{"faithfulness":50,"coverage":29,"coherence":15,"conciseness":5},"score":99,"quality_label":"EXCELLENT"}
```

## FACTUAL_ERROR

Peripheral error: the central event survives, only a detail is wrong. Stays in soft scoring.

Article: `市は5日、新しい図書館を開館した。総工費は12億円で、初日の来館者は3000人だった。`

Candidate: `市は5日、新しい図書館を開館した。総工費は20億円だった。`

Expected draft:

```json
{"claim_checks":[{"claim":"市が5日に新しい図書館を開館した","verdict":"SUPPORTED","source_evidence":"市は5日、新しい図書館を開館した"},{"claim":"総工費は20億円","verdict":"CONTRADICTED","source_evidence":"総工費は12億円"}],"dimensions":{"faithfulness":26,"coverage":18,"coherence":13,"conciseness":5},"score":62,"quality_label":"MIXED","issues":["Misstates the construction cost.","Omits the first-day attendance."]}
```

## FACTUAL_REVERSAL

Central reversal: the candidate is fluent and on topic, but asserts the opposite of the main event. Terminal, score 0. No deterministic gate or embedding can catch this; only the claim check can.

Article: `政府は5日、緊急事態宣言を全国に発令したと発表した。期間は3週間で、飲食店には営業時間の短縮を求める。`

Candidate: `政府は5日、緊急事態宣言の発令を見送ると発表した。飲食店への営業時間短縮の要請も行わない方針だ。`

Expected gate output:

```json
{"summary_id":"example","verdict":"NOT_GROUNDED","category":"FACTUAL_REVERSAL","article_evidence":["緊急事態宣言を全国に発令したと発表した","飲食店には営業時間の短縮を求める"],"candidate_evidence":["発令を見送ると発表した","要請も行わない方針だ"],"findings":["Reverses the article's central decision: the declaration was issued, not withheld."]}
```

Confirmed by the Reviewer, this becomes `{"eligible_for_soft_scoring":false,"terminal_result":"FACTUAL_REVERSAL","terminal_rank":0,"score":0,"quality_label":"HARD_FAIL_REVERSAL","dimensions":null}`.

## FABRICATED_CONTENT

Central fabrication: on topic and fluent, but the load-bearing claim exists nowhere in the article. Terminal, score 0.

Article: `消防によると、5日未明に博物館で火災が発生し、収蔵品の一部が焼失した。出火原因は調査中で、けが人はいない。`

Candidate: `警察は5日、博物館の火災が放火によるものと断定し、容疑者2人を逮捕したと発表した。`

Expected gate output:

```json
{"summary_id":"example","verdict":"NOT_GROUNDED","category":"FABRICATED_CONTENT","article_evidence":["出火原因は調査中"],"candidate_evidence":["放火によるものと断定し、容疑者2人を逮捕した"],"findings":["The arson determination and the two arrests appear nowhere in the article, which states the cause is still under investigation."]}
```

## LOW_COVERAGE

Article: `政府は大型減税案を可決した。対象は約500万世帯で、来年1月に始まる。野党は財源不足を批判した。`

Candidate: `野党は政府を批判した。`

Expected draft:

```json
{"dimensions":{"faithfulness":50,"coverage":5,"coherence":13,"conciseness":5},"score":73,"quality_label":"FINE","issues":["Omits the tax-cut approval, target population, and start date."]}
```

## INCOHERENT

Article: `チームは決勝で3対1で勝利し、初優勝した。監督は選手を称賛した。`

Candidate: `監督が称賛した。初優勝は3対1で、選手は決勝だった。`

Expected draft:

```json
{"dimensions":{"faithfulness":35,"coverage":18,"coherence":3,"conciseness":4},"score":60,"quality_label":"MIXED","issues":["Broken word order and dependencies make the event relationships unclear."]}
```

## VERBOSE

Article: `大学は来春、新しい工学部を開設する。定員は200人。`

Candidate: `大学は来春、新しい工学部を開設する予定だ。新しい学部は工学部であり、定員については200人という人数が設定されている。`

Expected draft:

```json
{"dimensions":{"faithfulness":50,"coverage":30,"coherence":13,"conciseness":1},"score":94,"quality_label":"EXCELLENT","issues":["Repetitive phrasing reduces conciseness."]}
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
{"decision":"REVISE","confidence":"HIGH","findings":["The death claim contradicts the article."],"suggested_dimensions":{"faithfulness":0,"coverage":12,"coherence":13,"conciseness":5}}
```
