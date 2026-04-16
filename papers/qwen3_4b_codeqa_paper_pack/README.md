# Qwen3 4B CodeQA Paper Pack

这个目录是新的论文写作工作区，只服务“写论文”。

当前定位：

- 会议稿：`code_qa` 作为标题级亮点，但正式主证据仍 anchored 在 `LongBench_3tasks canonical`
- 毕业稿：复用同一证据池，保留三任务全貌、系统设计、实验流程和工程实现
- 写作语言：中文主写
- 主稿格式：Markdown 优先

当前证据边界：

- 已验证并可直接引用：
  - `canonical` 单 seed 正式结果
  - `baseline_rag_4b` 与 `edge_agent_4b` 的正式对比
  - 单任务分解、关键图表、错误案例和运行日志
- 暂不作为正文既定事实：
  - `3-seed confirm`
  - `budget_matched`
  - `single_round_strong`
  - 新一轮补充实验

一句话主张：

> 本文不把故事写成“4B 小模型全面碾压”，而写成“在预算受限的长文档场景中，任务路由式 agent 协议显著提升 overall、multi-doc 和 code_qa，尤其在 code_qa 上收益突出，同时暴露出 single_doc 的特定失败模式与代价边界”。

## 从哪里开始

如果你现在要直接开写，推荐顺序：

1. 先看 [01_storyline.md](./01_storyline.md)
2. 再看 [05_key_data_snapshot.md](./05_key_data_snapshot.md)
3. 接着看 [03_source_of_truth.md](./03_source_of_truth.md)
4. 然后打开 [evidence/results_master_table.md](./evidence/results_master_table.md)
5. 最后进入会议稿骨架 [manuscript/conference_cn.md](./manuscript/conference_cn.md)

## 目录说明

- [00_manifest.md](./00_manifest.md)
  - 论文包内文件清单、状态、来源和用途
- [01_storyline.md](./01_storyline.md)
  - 论文故事线、研究问题、贡献边界、题目方向
- [02_claim_to_evidence_matrix.md](./02_claim_to_evidence_matrix.md)
  - 每个 claim 对应的结果、图表、案例和日志
- [03_source_of_truth.md](./03_source_of_truth.md)
  - 什么数字能用，什么数字不能当主结论用
- [04_writing_checklist.md](./04_writing_checklist.md)
  - 开写前和定稿前的检查清单
- [05_key_data_snapshot.md](./05_key_data_snapshot.md)
  - 当前最关键的正式数字、任务分解和随包快照说明

子目录：

- [manuscript/](./manuscript/)
  - 会议稿与毕业稿骨架、摘要题目变体、章节写作提示、局限性写法
- [evidence/](./evidence/)
  - 可直接引用的冻结结果页、任务分解、图表说明、案例摘要、方法比较
- [appendix/](./appendix/)
  - 附录主文件、`code_qa` 定位说明、相关工作与引文笔记
- [artifacts/](./artifacts/)
  - 随包走的原始结果快照，包含 CSV 和错误案例 JSONL
- [assets/](./assets/)
  - 随包走的图表原件，包含当前正式报告里的 PNG 文件

## 当前正式结果摘要

来源：

- 包内原始快照：
  - `artifacts/canonical_single_seed/metrics_table.csv`
  - `artifacts/canonical_single_seed/task_metrics.csv`
- 上游生成位置：
  - `report/formal_paper_canonical_s42_current/metrics_table.csv`
  - `report/formal_paper_canonical_s42_current/task_metrics.csv`

当前已验证数字：

| 方法 | overall F1 | single_doc | multi_doc | code_qa | P95 ratio | OOM |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_rag_4b` | 0.2552 | 0.2513 | 0.2104 | 0.2941 | 1.000 | 0 |
| `edge_agent_4b` | 0.3351 | 0.2150 | 0.2392 | 0.5020 | 1.333 | 3 |

直接解读：

- `overall` 明显提升：`+0.0799`
- `code_qa` 是当前最强亮点：`+0.2079`
- `multi_doc_qa` 为稳定正提升：`+0.0288`
- `single_doc_qa` 明确回撤：`-0.0363`

## 写作原则

- `canonical` 是唯一正式主结果来源
- 不再以旧初稿 `docs/25_论文实验章节初稿.md` 作为正文起点
- 不把“三任务全面平衡提升”写成既定事实
- `code_qa` 可以放进标题和摘要，但不能把整篇改写成纯代码论文
- 所有主稿数字优先从本目录的冻结结果页引用，而不是手工从 CSV 二次抄写

## 随包快照

为了让这个论文包在脱离仓库其他目录时也能独立使用，当前包内已经附带一份关键数据快照。

原始结果快照：

- `artifacts/canonical_single_seed/metrics_table.csv`
- `artifacts/canonical_single_seed/task_metrics.csv`
- `artifacts/canonical_single_seed/key_task_summary.csv`
- `artifacts/canonical_single_seed/error_cases.jsonl`

图表原件：

- `assets/figures/accuracy_bar.png`
- `assets/figures/cost_effect_curve.png`
- `assets/figures/retrieval_effect_curve.png`
- `assets/figures/gpu_mem_curve.png`
