# Title And Abstract Variants

## 题目候选

### 候选 1

`面向 4B 小模型长文档推理的预算感知任务路由协议：以 CodeQA 亮点和 Canonical 主证据为中心`

### 候选 2

`Budget-Aware Task-Routed Long-Document Reasoning for Qwen3 4B: Strong CodeQA Gains Under Canonical Evaluation`

### 候选 3

`小模型不是小一号大模型：面向长文档任务异质性的 4B 任务路由式协议`

### 候选 4

`在预算受限下提升 4B 长文档推理：一个以 CodeQA 为亮点的任务路由式 Agent 协议`

## 摘要短版

> 本文研究 `Qwen3 4B` 在预算受限条件下的长文档推理。我们观察到 `single_doc_qa`、`multi_doc_qa` 与 `code_qa` 的失败模式并不一致，统一单轮 RAG 难以同时兼顾不同任务。为此，本文提出一种 `budget-aware task-routed protocol`，通过任务感知的检索晋级、有限步迭代和事实记忆机制，在不扩大模型规模的前提下提高整体效果。在 `LongBench_3tasks canonical` 的单 seed 正式评测中，所提方法将 overall F1 从 `0.2552` 提升到 `0.3351`。其中，`code_qa` 从 `0.2941` 提升到 `0.5020`，`multi_doc_qa` 从 `0.2104` 提升到 `0.2392`；同时，`single_doc_qa` 从 `0.2513` 回落至 `0.2150`。结果表明，任务路由式协议能显著放大小模型在代码与跨文档场景中的收益，但其在单文档场景中的边界同样需要被显式报告。

## 摘要长版

> 长文档任务对小模型提出了比短上下文更复杂的挑战：模型不仅要在有限预算下定位证据，还要在不同任务中采用不同的检索与推理策略。本文聚焦 `Qwen3 4B`，讨论预算受限条件下的小模型长文档推理问题。我们认为，小模型在 `single_doc_qa`、`multi_doc_qa` 与 `code_qa` 上的失败模式具有显著异质性，因此统一的单轮检索生成流程往往会牺牲关键任务收益。基于此，本文提出一种 `budget-aware task-routed protocol`，其核心包括任务感知的检索晋级、有限步迭代、事实记忆和提前停止机制。在 `LongBench_3tasks canonical` 的单 seed 正式评测中，相比标准 `baseline_rag_4b`，所提方法将 overall F1 从 `0.2552` 提升到 `0.3351`。进一步的任务分解表明，方法在 `code_qa` 上获得最显著收益，从 `0.2941` 提升到 `0.5020`，在 `multi_doc_qa` 上也取得稳定正提升；但在 `single_doc_qa` 上仍存在回撤。该结果说明，对小模型而言，长文档推理的关键不只是更强的统一策略，而是任务感知的协议设计。本文同时报告收益伴随的时延与 OOM 代价，以给出更完整的结果边界。

## 贡献点短写法

1. 提出面向 `Qwen3 4B` 长文档场景的任务路由式预算协议。
2. 在 `canonical` 正式评测上获得明显 overall 提升，并在 `code_qa` 上实现大幅收益。
3. 揭示协议在 `single_doc` 上的失配边界，强调小模型长文档推理中的任务异质性。

