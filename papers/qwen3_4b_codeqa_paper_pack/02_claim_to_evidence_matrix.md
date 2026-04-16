# 02 Claim To Evidence Matrix

本页的作用是防止正文 claim 超出当前证据边界。

## 可用 claim

| Claim ID | 可以怎么写 | 证据来源 | 状态 |
| --- | --- | --- | --- |
| C1 | `edge_agent_4b` 在 `canonical` 单 seed 上优于 `baseline_rag_4b` 的 overall F1 | `report/formal_paper_canonical_s42_current/metrics_table.csv` | verified |
| C2 | 当前最大收益来自 `code_qa` | `report/formal_paper_canonical_s42_current/task_metrics.csv` | verified |
| C3 | `multi_doc_qa` 存在正向收益 | `report/formal_paper_canonical_s42_current/task_metrics.csv` | verified |
| C4 | `single_doc_qa` 出现回撤，说明协议仍有任务边界 | `report/formal_paper_canonical_s42_current/task_metrics.csv` | verified |
| C5 | 收益伴随额外时延和少量 OOM 风险 | `metrics_table.csv` + `task_metrics.csv` | verified |
| C6 | 当前故事更适合写成“任务异质性 + code_qa 亮点 + canonical 主证据” | `metrics_table.csv` + `task_metrics.csv` + `docs/41_paper_canonical_execution_log_2026-04-16.md` | verified |
| C7 | 方法在 `code_qa` 上的改进不是单个样例现象，存在多条强正例 | `results/*jsonl` + `error_cases` 分析 | verified |

## 谨慎 claim

| Claim ID | 可以怎么写 | 使用条件 | 当前状态 |
| --- | --- | --- | --- |
| W1 | 当前结论为单 seed 正式结论，尚未完成 `3-seed confirm` | 必须在文中明说 | usable with caveat |
| W2 | `code_qa` 可以放到标题或摘要亮点位 | 必须同时说明正式主证据仍为 `canonical` | usable with caveat |
| W3 | 方法体现了任务感知协议比统一单轮流程更合适 | 需要结合案例与单任务分解一起写 | usable with caveat |

## 当前不能写成既定事实的 claim

| Claim ID | 不要这样写 | 原因 |
| --- | --- | --- |
| N1 | 三任务全面平衡提升 | `single_doc_qa` 明确回撤 |
| N2 | 强对照已经全部跑完且全部被超过 | `budget_matched` 与 `single_round_strong` 当前未形成正式结果 |
| N3 | 结论已通过 `3-seed + CI` | 当前没有 |
| N4 | 方法在所有长文档任务上普遍更优 | 现有结果不支持 |
| N5 | 这是纯代码论文 | 正式主证据依然来自三任务 canonical |

## 图表与 claim 对应

| 证据 | 支撑什么 claim |
| --- | --- |
| `evidence/results_master_table.md` | C1, C5 |
| `evidence/task_breakdown.md` | C2, C3, C4 |
| `evidence/figures_manifest.md` | C1, C5 |
| `evidence/error_case_digest.md` | C3, C4, C7 |
| `appendix/codeqa_positioning.md` | C6, W2 |

