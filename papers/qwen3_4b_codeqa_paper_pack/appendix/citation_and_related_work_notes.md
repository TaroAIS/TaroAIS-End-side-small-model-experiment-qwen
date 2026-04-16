# Citation And Related Work Notes

本页不是正式参考文献，而是写相关工作时的分组与补充清单。

## 当前 `references.bib` 的状态

目前仓库里的 `references.bib` 还非常薄，只包含：

- `Qwen3`
- `MiniLongBench`
- 少量训练工具文档

这意味着：

- 你可以开始写正文
- 但在投稿或送审前，必须补齐正式引用

## 建议补充的相关工作分组

### 1. 长文档评测基准

建议补：

- `LongBench`
- `Lost in the Middle`
- `NarrativeQA`
- `HotpotQA`
- `MuSiQue`

作用：

- 解释为什么长文档与跨文档任务不是普通 QA 的重复

### 2. 代码理解与仓库级评测

建议补：

- `RepoBench`
- 与代码补全/仓库问答相关的基准或代表性工作

作用：

- 说明为什么 `code_qa` 是高价值亮点任务

### 3. 小模型与预算受限推理

建议补：

- 与小模型 test-time reasoning
- budget-aware inference
- resource-constrained deployment

作用：

- 解释为什么本文强调 `4B` 与预算约束

### 4. Agent / 多步推理 / 检索协议

建议补：

- 多步推理
- 检索增强 agent
- 自适应检索或 test-time compute allocation

作用：

- 解释本文为什么不是普通单轮 RAG

## 写相关工作时的落点

### 推荐写法

- 现有工作大多分别讨论长文档、代码任务、或 agent 机制
- 本文更关注三者交叉：`4B`、预算约束、任务异质性、`code_qa` 亮点

### 不推荐写法

- 罗列一堆不服务于本文问题的通用大模型工作
- 把所有 agent 类工作都硬说成直接相关

## 定稿前必须做的事

- 把上述分组中的正式论文与数据集引用补入 `references.bib`
- 确保正文出现的基准、模型和任务都有正式条目
- 不要只保留 GitHub 页面对论文投稿是不够的

