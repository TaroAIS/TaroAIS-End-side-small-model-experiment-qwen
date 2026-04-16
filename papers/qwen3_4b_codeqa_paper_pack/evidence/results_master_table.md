# Results Master Table

本页是当前论文包的主结果冻结页。正文优先引用这里，不要再手工从 CSV 抄数字。

## 1. 正式主表（当前 verified）

来源：

- `report/formal_paper_canonical_s42_current/metrics_table.csv`
- `report/formal_paper_canonical_s42_current/task_metrics.csv`

当前正式主表只包含已经 verified 的方法：

| 方法 | overall F1 | single_doc | multi_doc | code_qa | p50 latency(s) | p95 latency(s) | P95 ratio | avg_steps | avg_retrieval | OOM | 备注 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `baseline_rag_4b` | 0.2552 | 0.2513 | 0.2104 | 0.2941 | 26.24 | 41.44 | 1.000 | 1.0000 | 1.0000 | 0 | anchor |
| `edge_agent_4b` | 0.3351 | 0.2150 | 0.2392 | 0.5020 | 36.03 | 55.23 | 1.333 | 1.8647 | 2.7878 | 3 | current verified main method |

## 2. 关键增量

| 指标 | 变化 |
| --- | ---: |
| overall F1 | `+0.0799` |
| single_doc_qa F1 | `-0.0363` |
| multi_doc_qa F1 | `+0.0288` |
| code_qa F1 | `+0.2079` |
| p95 latency ratio | `1.333` |
| OOM | `0 -> 3` |

## 3. code-centric 辅助表

如果会议稿希望更突出 `code_qa` 和高价值任务组合，可以使用下面这张辅助表，但不能替代主表。

来源：

- `report/formal_paper_canonical_s42_current/key_task_summary.csv`

| 组合任务 | baseline | edge_agent | delta | p95 ratio |
| --- | ---: | ---: | ---: | ---: |
| `multi_doc_qa + code_qa` macro F1 | 0.2522 | 0.3706 | `+0.1183` | 1.400 |

## 4. 推荐正文写法

### 主结果一句话

> 在 `LongBench_3tasks canonical` 的当前单 seed 正式评测中，`edge_agent_4b` 将 overall F1 从 `0.2552` 提升到 `0.3351`，显示出在预算受限 4B 条件下的显著整体收益。

### `code_qa` 亮点一句话

> 当前最显著的收益来自 `code_qa`，其 F1 从 `0.2941` 提升到 `0.5020`，提升幅度达到 `+0.2079`。

### 诚实边界一句话

> 需要同时指出的是，`single_doc_qa` 从 `0.2513` 回落到 `0.2150`，说明统一 agent 协议在不同长文档任务上的最优策略并不一致。

## 5. 当前表格不要怎么用

- 不要把这张表写成“全部实验已经完成后的最终表”
- 不要把空缺的强对照行想象成已验证
- 不要把 `code_qa` 辅助表替代正式主表
- 不要把本页结论写成“三任务全面平衡提升”

