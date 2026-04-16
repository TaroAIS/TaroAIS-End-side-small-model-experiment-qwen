# 会议论文主稿骨架（中文）

## 题目候选

优先从 `title_abstract_variants.md` 里选，不要临时另起口径。

推荐方向：

- `4B` 小模型
- 长文档
- budget-aware task-routed protocol
- `code_qa` 亮点

## 摘要

可直接改写的基底版本：

> 长文档场景下，小模型的失败模式并非单一现象，不同任务往往需要不同的推理与检索策略。本文关注 `Qwen3 4B` 在预算受限条件下的长文档问答与代码理解问题，提出一种 `budget-aware task-routed protocol`，通过任务感知的检索晋级、有限步迭代和事实记忆机制，替代统一的单轮检索生成流程。在 `LongBench_3tasks canonical` 上，所提方法相对标准 `baseline_rag_4b` 将 overall F1 从 `0.2552` 提升到 `0.3351`。其中，`code_qa` 从 `0.2941` 提升到 `0.5020`，`multi_doc_qa` 从 `0.2104` 提升到 `0.2392`，显示出在关键高价值任务上的明显收益。同时，我们也观察到 `single_doc_qa` 从 `0.2513` 回落至 `0.2150`，说明统一 agent 协议在不同长文档任务上的最优策略并不一致。结果表明，在不扩大模型规模的前提下，任务路由式协议能够显著提高小模型在长文档中的整体效能，但其收益与代价边界需要被一并报告与分析。

## 1. 引言

### 要回答的问题

- 为什么 `4B` 小模型值得研究，而不是直接讨论更大模型
- 为什么长文档任务不能被统一单轮 RAG 吸收
- 为什么 `code_qa` 能成为标题级亮点，但主证据仍应 anchored 在 canonical

### 推荐写法

第一段：

- 写长文档推理的现实约束：预算、时延、部署代价
- 引出小模型不是“更弱的大模型”，而是需要不同协议

第二段：

- 引出任务异质性
- `single_doc_qa / multi_doc_qa / code_qa` 的最优策略不一致

第三段：

- 引出现有统一单轮 RAG 的不足
- 引出本文的任务路由式协议

第四段：

- 摘出正式结果
- 明说 `overall` 和 `code_qa` 的收益
- 同时交代 `single_doc` 回撤，建立诚实口径

### 可直接放进引言末尾的贡献

1. 提出适配 `Qwen3 4B` 长文档场景的 `budget-aware task-routed protocol`。
2. 在 `LongBench_3tasks canonical` 上获得显著 overall 提升，并在 `code_qa` 上取得大幅收益。
3. 报告方法的收益边界，说明 `single_doc_qa` 仍存在明显挑战。

## 2. 相关工作

建议分四类写：

1. 长文档基准与评测
2. 长上下文中的检索增强与 test-time reasoning
3. 小模型 / 预算受限推理
4. 代码理解与仓库级问答

写法要求：

- 不写成大而全综述
- 每类只服务于你的问题定义
- 结尾要落回：现有工作很少把“任务异质性 + 小模型预算协议 + code_qa 亮点”放在同一条线里

## 3. 方法

### 3.1 问题设定

- 模型固定：`Qwen3 4B`
- 数据正式主结论：`LongBench_3tasks canonical`
- 任务分组：`single_doc_qa / multi_doc_qa / code_qa`

### 3.2 协议概述

要解释的不是“系统多复杂”，而是协议为什么要分任务处理：

- 初始任务感知
- 检索晋级与预算分配
- 有限步迭代
- 事实记忆
- 提前停止与成本控制

### 3.3 为什么会对 `code_qa` 更有效

这里是会议稿亮点位，建议突出：

- 代码任务更依赖跨片段定位与局部精确匹配
- 单轮 RAG 容易给出局部相似但非目标片段
- agent 协议在 `code_qa` 中提供更明显的收益空间

## 4. 实验设置

### 4.1 数据与口径

- 正式主结论：`canonical`
- 当前结论是单 seed 正式结果
- monitor 集和附录集不进入主结论

### 4.2 对照组

当前正文建议只写当前 verified 的对照：

- `baseline_rag_4b`
- `edge_agent_4b`

然后在文中诚实说明：

- 更强控制基线是理想补充，但当前 package 的正式主结论不依赖它们

### 4.3 指标

- `overall F1`
- 各任务 F1
- `p95 latency`
- `OOM`

## 5. 主结果

正文必须放主表。

推荐先放 [../evidence/results_master_table.md](../evidence/results_master_table.md) 中的 verified 表，再接任务分解。

### 5.1 主表解读

可直接写的结论：

- `overall` 提升 `+0.0799`
- `code_qa` 提升 `+0.2079`
- `multi_doc_qa` 提升 `+0.0288`
- `single_doc_qa` 回撤 `-0.0363`

### 5.2 结果解读重点

- 本文最强结论不是“三任务都赢”
- 而是“在 canonical 正式评测上，协议把平均效果和关键亮点任务明显拉起来”
- 同时结果揭示了 `single_doc` 的失败模式

## 6. 分析与案例

建议分三段：

1. `code_qa` 正例
2. `multi_doc_qa` 正例
3. `single_doc_qa` 失败模式

素材入口：

- [../evidence/error_case_digest.md](../evidence/error_case_digest.md)

## 7. 局限性与威胁

必须正面写：

- 当前是单 seed 正式结论
- `single_doc` 存在回撤
- `OOM=3`
- `code_qa` 虽然样本数充足，但来源仍偏 `lcc + repobench-p`

完整写法参考：

- [limitations_and_threats.md](./limitations_and_threats.md)

## 8. 结论

结论不要写成“全面成功”，而要写成：

- 任务路由协议对 4B 长文档推理是有价值的
- 其收益集中体现在 `overall`、`multi_doc` 和尤其 `code_qa`
- 未来工作应重点解决 `single_doc` 的协议失配问题

