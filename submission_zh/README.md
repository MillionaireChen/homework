# 提交物 — 日语新闻摘要质量评估

同一套「不依赖参考答案」的评估设计,做了两遍独立实现,各自跑完全部 250 条,然后互相交叉验证。

**请先看 [`report.md`](report.md)**,它是首要产出。

---

## 目录内容

```
submission/
├── report.md                  首要产出:探索、设计、验证、局限
├── processing.md              边做边写的决策日志:假设、纠正、走过的死路
├── DESIGN.md                  收尾时的设计定稿
├── scores.jsonl               250 行,每个 summary_id 一行,同一行含两套实现的结果
├── cross_validation.json      两套实现一致性的机器可读统计
├── figures/
│   ├── funnel_architecture   三层漏斗架构        .png .svg .drawio
│   ├── funnel_results        结果与交叉验证      .png .svg .drawio
│   ├── failure_modes         失败模式分类        .png .svg .drawio
│   └── *.png                 运行产出的结果图表(漏斗、分数、类别、
│                             参考答案验证、两套实现一致性)
├── code/
│   ├── implementation_a_claude/   Claude Code 插件:skill、4 个 agent、脚本
│   ├── implementation_b_gpt/      GPT/Codex 插件:skill、agent、脚本
│   ├── exploration/               数据探索与嵌入阈值校准
│   ├── cross_validation/          compare_implementations.py
│   └── figures/                   make_diagrams.py —— 重新生成三张图
└── runs/
    ├── implementation_a_claude_full250/   完整审计轨迹:各道门、复核、草稿、判定
    └── implementation_b_gpt_full250/      同上,第二套实现
```

另有两份文档记录了工作实际推进的过程,包括被放弃的方案和我必须做出的纠正:
[`processing.md`](processing.md)(边做边写的决策日志)与 [`DESIGN.md`](DESIGN.md)(收尾时的设计定稿)。

## scores.jsonl 格式

每行一个 JSON 对象,每个 `summary_id` 一行,共 250 行。

| 字段 | 含义 |
|---|---|
| `summary_id`、`article_id` | 关联键 |
| `score` | **主分数,0–100**,取自实现 A。被终止的候选记 0 分 |
| `quality_label` | `EXCELLENT` 90-100、`GOOD` 75-89、`FINE` 65-74、`MIXED` 50-64、`POOR` 0-49,或终止类别 |
| `terminal_result` | `null`,或 `OFF_TOPIC` / `FACTUAL_REVERSAL` / `FABRICATED_CONTENT` / `VERBATIM_SOURCE_COPY` / `OBVIOUS_TRUNCATION` |
| `terminal_rank` | 被终止候选的严重度层级:0 最差 → 3 最轻 |
| `dimensions` | `faithfulness` /50、`coverage` /30、`coherence` /15、`conciseness` /5;终止时为 `null` |
| `rank_within_article` | 篇内名次 1–5 |
| `implementation_a_claude`、`implementation_b_gpt` | 两套实现各自的判定 |
| `implementations_agree_on_routing` | 两边是否都终止、或都给分 |
| `score_delta` | 两边都给分时,A 减 B |

`score` 在篇内和跨篇都可比:各维度是绝对刻度,锚点按篇重新生成、不在文章之间沿用。

`runs/` 下的逐次运行文件保留了每一行的完整证据——带原文引用片段的 claim 核查、各道门的提议、复核者的判定,以及逐阶段的轨迹。

## 如何运行

两套实现**都是插件**。装好之后给它一条指令,插件会自己跑完整条级联,并派出自己的门禁、评分、复核、报告 agent。下面提到的所有阶段都是这些 agent 内部执行的——**你不需要手动驱动任何一步**。

### 实现 A — Claude Code 插件

安装配置见 `code/implementation_a_claude/settings.json.example`;在工作仓库里它位于 `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "local": { "source": { "source": "directory", "path": "./plugin_claude" } }
  },
  "enabledPlugins": { "summary-quality-funnel@local": true }
}
```

用 Claude Code 打开本仓库,插件即加载。在交互式终端里也可以改用
`/plugin marketplace add ./plugin_claude` 再 `/plugin install summary-quality-funnel@local`。

然后一条命令:

```
/summary-quality-funnel:evaluate-summaries evaluate all 250 pairs in data/
```

复现步骤到此为止。这条命令会跑物理门、嵌入提示、grounding gate、按篇生成锚点、评分与独立复核,然后校验、排序、出图、出报告。插件提供四个 agent——`summary-grounding-gate`、`summary-scorer`、`summary-reviewer`、`summary-reporter`——外加第五个 `summary-reviewer-blind`,它已提交但在本次运行中**刻意未启用**(见「局限」)。

### 实现 B — Codex 插件

清单在 `code/implementation_b_gpt/summary-quality-funnel/.codex-plugin/plugin.json`,按 Codex 安装本地插件的常规方式装。装好后它会在命令列表里显示为两个可直接调用的条目:

- **Summary Quality Funnel** — 硬约束门、带复核的评分、报告 agent、审计轨迹
- **Summary Report Agent** — 运行固定的报告代码,只由 agent 撰写结论部分

选 funnel 那一项,把批次交给它:

```
Evaluate and rank all 250 article-summary pairs in data/, then generate the chart report.
```

形态与实现 A 相同:一次调用,插件自行派出 Scorer、Reviewer、Report 子 agent 完成整条级联。

### agent 依赖的环境

```bash
python3 -m venv .venv && .venv/bin/pip install numpy requests matplotlib
ollama pull qwen3-embedding:0.6b     # 可选
```

嵌入阶段只产生提示、永远不构成终止,所以没有 Ollama 也能跑完——实现 B 自己那次全量 250 条运行,就是在嵌入阶段不可用的情况下完成的。

### 不重跑的前提下查验或重算结果

各插件的确定性部分都是普通脚本,可以直接对已提交的运行产物重放:

```bash
S=submission/code/implementation_a_claude/summary-quality-funnel/skills/evaluate-summary-quality/scripts
.venv/bin/python $S/validate_result.py    runs/implementation_a_claude_full250/score.jsonl
.venv/bin/python $S/rank_results.py       --input  runs/implementation_a_claude_full250/score.jsonl \
                                          --output /tmp/ranked.jsonl
.venv/bin/python $S/make_report_charts.py --input /tmp/ranked.jsonl --outdir /tmp/figs
```

重新生成三张说明图(SVG,装了 ImageMagick 时同时出 PNG):

```bash
.venv/bin/python submission/code/figures/make_diagrams.py --outdir submission/figures
```

`.drawio` 文件保存同样的图供手工编辑;报告嵌入的是 PNG——markdown 的图片语法无法指向 drawio XML。

两套实现的交叉验证是单个脚本,不需要任何 agent:

```bash
.venv/bin/python submission/code/cross_validation/compare_implementations.py \
  --claude runs/implementation_a_claude_full250/score_ranked.jsonl \
  --gpt    runs/implementation_b_gpt_full250/score.jsonl \
  --articles ../data/articles.jsonl --summaries ../data/summaries.jsonl \
  --outdir cross_validation/
```

**参考答案从不进入运行时路径。** `hard_gate.py` 会剥离该字段,`validate_result.py` 会拒绝任何含该字符串的输出。它们只在两个离线场合被读取,且都在评分定稿之后:弱标签检验,以及本交叉验证。

## AI 工具的使用情况

助手负责实现、跑批和起草。**架构是我定的**,我在通往它的路上试过又放弃的那些方案,也一并记在这里。

### 设计决定由我做出

- **级联漏斗本身。** 是我提出的:便宜的确定性检测在前,嵌入其次,模型判断最后,每一道只处理上一道剩下的。理由也是我的——成本、延迟,以及**确定性的拒绝可解释,而概率性的拒绝不可解释**。提前退出是它的直接结果:250 条里有 80 条根本没走到最贵的两个阶段。
- **硬约束与软约束的划分。** 我的框架。违反硬约束直接定性;软约束只给幸存者分级。输出的两层结构——带层级的终止类别 + 0–100 分数——由此而来。
- **参考答案不得进入评估路径。** 助手最初的设计把它当作覆盖度比较基准和排序锚点。我否决了:生产环境的请求里没有参考答案。这一条把"基于参考答案的合奏"改成了"不依赖参考答案的漏斗",是本项目影响最大的单个决定。
- **抄袭检测归字符串匹配,不归嵌入**——嵌入给逐字照抄打的分是全场最高,用它检测等于奖励这种失败。
- **把设计做两遍并交叉验证。** 我提的,它产生了本次提交中最强的证据。
- **参考答案的可达性。** 全量跑完之后我发现:复核者仍然能自己打开含参考答案的语料文件——那时的保证是一条约定,不是一个性质。我要求做一个 corpus-blind 复核者,然后**刻意把启用它推到下一版**并挂上明确的测量指标,而不是让开发无止境地做下去。
- **范围与收尾。** 跑哪些实验、什么结果算够了、什么时候停。

### 我提出过、但最终没有采用的方案

记录在此,因为这些否决对设计的塑造不亚于那些采纳。全部连同当时的理由保存在 `processing.md`。

- **四路加权合奏**——人工 0.4、专家 agent 0.2、claim 级核查 0.2、规则层 0.2。放弃原因:**含人工项的分数无法在新数据上运行**;而且把规则层降格成 0.1 的投票者,恰好丢掉了它唯一的长处——它能定夺。
- **对全部 250 条做人工标注**,切成 dev 与封存两半,用来提炼专家规则再移植进 judge 的提示词。在确定性层被证明能独立解决 84 条之后,按成本放弃;而且分数里含人工项,与"不依赖参考答案"的目标是同一种失效。
- **拿参考答案当 ground truth 来低成本构造黄金集。** 很有吸引力,但作业里明文警告过。最终只保留为评分定稿之后的离线弱标签检验。
- **Cross-encoder reranker(BGE)。** 我要求试一下。试了,在全部 250 条上:它在跑题集合上与嵌入门禁 16/16 一致,没有带来任何新信息,代价是 2GB 模型和慢得多的推理。作为交叉验证证据保留,从流水线里去掉。
- **把"候选 ↔ 生成锚点"的嵌入相似度当评分特征。** 量过了,结果混杂,放弃。

### AI 辅助完成的部分

实现脚本与 agent 提示词;执行 250 条评估;为便于我阅读而翻译语料;计算统计量与绘图;在我审阅过结果之后起草本 README 与报告。

### 实质影响了结果的互动

参考答案的纠正,以及随后的一个后续错误——助手把 `reference_summary` 描述成"文章里疑似摘要的段落",把讨论带偏到"抄它算不算抄袭";我纠正了它,并要求把这个错误**写进 `processing.md`**,而不是悄悄改掉。硬/软约束的框架。把截断改为按比例扣分而非终止的决定——这正是两套实现之间唯一那处成文分歧的来源。以及参考答案可达性的发现,它被作为一个公开的局限记录下来,而不是被包装成已解决。

## 对本工作成立范围的诚实总结

在 141 条可判定记录上与弱标签一致率 91.5%;50 篇文章篇内排序零倒置;两套独立实现之间路由一致率 90.0%、分数相关 0.897;字节相同的候选对上 6/6 得分完全一致。

它**不足以**证明生产可用:单一语料、单一语言、没有人工排序对照、43% 的语料无标签,而且「不依赖参考答案」这个保证目前建立在约定而非构造之上。报告的「局限」一节把每一条都写明了,并附上了能关闭它的那个测量。
