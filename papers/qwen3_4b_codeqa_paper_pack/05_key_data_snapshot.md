# 05 Key Data Snapshot

本页是当前论文包里最值得先看的“关键数字快照页”。

## 当前主结论

- 数据口径：`LongBench_3tasks canonical`
- 结果边界：单 seed 正式结果
- 当前已验证方法：`baseline_rag_4b` vs `edge_agent_4b`

## 关键数字

| 指标 | baseline | edge_agent | delta |
| --- | ---: | ---: | ---: |
| overall F1 | 0.2552 | 0.3351 | `+0.0799` |
| single_doc_qa | 0.2513 | 0.2150 | `-0.0363` |
| multi_doc_qa | 0.2104 | 0.2392 | `+0.0288` |
| code_qa | 0.2941 | 0.5020 | `+0.2079` |
| p95 latency(s) | 41.44 | 55.23 | ratio `1.333` |
| OOM | 0 | 3 | `+3` |

## 三句最重要的话

> `edge_agent_4b` 在当前 verified 的 canonical 单 seed 正式评测中，将 overall F1 从 `0.2552` 提升到 `0.3351`。

> `code_qa` 是当前最显著的亮点任务，F1 从 `0.2941` 提升到 `0.5020`。

> `single_doc_qa` 从 `0.2513` 回落到 `0.2150`，说明当前协议仍有明确边界。

## 包内自带的原始快照

CSV：

- `artifacts/canonical_single_seed/metrics_table.csv`
- `artifacts/canonical_single_seed/task_metrics.csv`
- `artifacts/canonical_single_seed/key_task_summary.csv`

图表：

- `assets/figures/accuracy_bar.png`
- `assets/figures/cost_effect_curve.png`
- `assets/figures/retrieval_effect_curve.png`
- `assets/figures/gpu_mem_curve.png`

案例：

- `artifacts/canonical_single_seed/error_cases.jsonl`
