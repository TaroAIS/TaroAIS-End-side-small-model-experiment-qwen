# Method Comparison Notes

本页用于解释“不同方法各自在回答什么问题”。

## 当前已验证方法

### `baseline_rag_4b`

定义：

- 标准单轮检索 + 生成
- 当前最稳的 anchor

它回答的问题：

- 如果不给 4B 小模型增加协议复杂度，标准 RAG 能做到什么水平？

### `edge_agent_4b`

定义：

- 任务路由式协议
- 带有限步迭代、检索晋级、事实记忆、提前停止和预算守卫

它回答的问题：

- 在同一 4B 模型和同一数据口径下，协议设计能否换来更高 overall 和关键任务收益？

## 当前 package 不依赖但可以提及的理想对照

### `baseline_budget_matched_4b`

理想作用：

- 回答收益是否只是因为“花了更多检索/生成预算”

### `baseline_single_round_strong_4b`

理想作用：

- 回答收益是否只是因为“单轮检索更强”

## 写作建议

### 会议稿现在能稳写的比较

- `baseline_rag_4b` vs `edge_agent_4b`

### 可以提但不能写成已验证事实的比较

- `budget matched`
- `single-round strong`

推荐措辞：

> 更强控制基线是自然且重要的补充，但当前 package 的正式结论建立在已验证的 baseline-agent 对比之上。

## 当前比较结论

| 维度 | `baseline_rag_4b` | `edge_agent_4b` |
| --- | --- | --- |
| overall | 较低 | 更高 |
| `code_qa` | 明显不足 | 显著提升 |
| `multi_doc_qa` | 一般 | 稳定更优 |
| `single_doc_qa` | 更稳 | 回撤 |
| 时延 | 更低 | 更高 |
| OOM | 0 | 3 |

一句话总结：

> 当前 agent 的价值不是“全方位更优”，而是“用额外协议换取 overall、multi-doc 和尤其 code_qa 的显著收益，同时付出 single-doc 和成本方面的代价”。

