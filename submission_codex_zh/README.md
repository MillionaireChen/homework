# 摘要质量评估器——Codex 中文核对版

这是 Codex 实现的中文核对版，面向 LLM 应用评估设计作业。它评估 250 条日文新闻摘要（50 篇文章、每篇 5 条候选摘要），并在 [`scores.jsonl`](scores.jsonl) 中为每个 `summary_id` 输出一条结果。

## 通过 Plugin 复现

两个实现都是通过 plugin 运行的，而不是直接执行独立评分脚本。复现 Codex 版本时，将 [`code/summary-quality-funnel`](code/summary-quality-funnel) 安装到 Codex 中，准备好作业提供的 `data/` 目录，然后使用以下斜杠命令：

```text
/summary-quality-funnel:evaluate-summary-quality
```

该命令会启动完整漏斗，并生成 JSONL、审计轨迹、图表和报告。Claude 版本则独立使用 `../plugin_claude/summary-quality-funnel` 中的 plugin，并执行：

```text
/summary-quality-funnel:evaluate-summaries
```

两个 plugin 分别安装、分别运行；评分阶段互相看不到对方的输出。只有两个最终 JSONL 都生成后，才进行离线交叉验证。随附的 Python 文件是 plugin 使用的验证和报告辅助代码，不是主要的用户入口。

## 交付物

- [`report.md`](report.md)：中文报告，用于核对英文最终报告的含义。
- [`scores.jsonl`](scores.jsonl)：250 条最终评分结果。
- [`diagrams/`](diagrams/)：可编辑的 Draw.io 文件及其渲染预览。
- [`figures/`](figures/)：由最终 JSONL 确定性生成的统计图表。
- [`run_artifacts/cross_validation.json`](run_artifacts/cross_validation.json)：Claude 与 Codex 的独立实现交叉验证结果。

## AI 工具说明

Grounding Gate、Scorer、Reviewer 和 Report 角色由 Codex agents 执行。本地 embedding 服务只用于文章与其自身候选摘要之间的相关性证据；运行时没有使用本地生成模型，也没有向评估器提供 reference summary。评估设计、硬/软约束划分、终止策略和验证标准由人工决定，并在 AI 协助下迭代完善。
