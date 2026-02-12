# Qwen3 端侧推理 + 小模型蒸馏 完整实验工程

更新日期：2026-02-12

本仓库已经从模板阶段升级为可执行、可复现实验工程，目标是验证：
- 在关键任务（`multi_doc_qa + code_qa`）上，`edge_agent` 是否相对 `baseline_rag` 提升效果；
- 同时满足“代价可接受”的成本门槛（延迟/检索开销）。

## 当前仓库状态
- 主实验链路（A-D）：`prepare -> index -> baseline -> agent -> evaluate`
- Student 链路（E）：`distill -> train_student -> eval_student`
- 消融：`think_off` / `iterative_off` / `memory_sliding` / `inj_defense_off`
- 关键任务结论：多 seed、`95% CI`、门槛判定（`report_key/decision_gate.json`）

## 快速开始（工程运行）
1) 先跑 smoke（链路验证，允许 fallback/mock）：
- `bash scripts/cmd/smoke.sh`

2) 再跑 formal（论文主实验，严格失败语义）：
- `bash scripts/cmd/all.sh`

3) 跑关键任务多 seed 结论实验（默认 42/123/2026）：
- `bash scripts/cmd/bench_key_tasks.sh`

脚本文档：`scripts/cmd/README.md`

## 实验视角总览
- 主对比：`baseline_rag` vs `edge_agent`
- 主实验口径：`run_mode=formal` + `retrieval_scope=sample`
- `global` 检索范围仅用于扩展实验，不混入主表
- 关键任务聚合默认：`key_tasks=multi_doc_qa code_qa` + `key_agg=macro`

## 结果如何读
主结论建议读取顺序：
1) `report_key/decision_gate.json`
2) `report_key/seed_aggregate.csv`
3) `report_key/seed_<n>/key_task_summary.csv`

门槛（中等严格）：
- `delta_f1_key >= 0.03`
- `latency_ratio <= 1.5`
- `retrieval_ratio <= 1.8`

判定逻辑：三个条件同时满足才算通过。

## 当前结果快照说明（2026-02-12）
- 当前仓库包含已运行产物快照（`report_tiny/`、`report_key/`、`results/run_*`）。
- 这些快照会随复跑变化，不应当作固定真值。
- `report_key` 当前快照来自 smoke 环境链路验证，显示门槛未通过：
  - `delta_f1_key_mean = -0.0625`
  - `latency_ratio_key_mean = 3.6258`
  - `retrieval_ratio_key_mean = 3.5`
- 只有 `formal + sample + multi-seed` 的结果才用于论文主结论。

## 数据来源与版本
### Smoke 数据
- `smoke_data/minilongbench_tiny.jsonl`
- 3 条样本：`single_doc_qa` / `multi_doc_qa` / `code_qa`

### 正式数据
- 数据源：Hugging Face `linggm/MiniLongBench`
- 上游项目：`https://github.com/MilkThink-Lab/MiniLongBench`
- 固定 revision：`0ba7bf46265f1f783653693fb6b581f617f37275`
- 输出路径：`data/minilongbench_{split}.jsonl`
- 来源追溯：`data/minilongbench_source.json`

## 文档入口
- 实验主手册：`docs/23_experiment_playbook.md`
- 更新记录：`docs/22_experiment_update_2026-02-12.md`
- 文档索引：`docs/README.md`
- 命令与流程：`scripts/cmd/README.md`

## 目录说明
- `docs/`：实验设计、解释口径、更新与论文映射
- `configs/`：超参配置
- `schemas/`：数据/结果/metadata/facts 的 JSON Schema
- `templates/`：表格模板与图文件清单
- `scripts/`：一键执行脚本与辅助脚本

## 历史附录
- `codex/` 目录保留为历史生成提示与验收清单归档。
- 当前仓库主入口以可执行实验流程和实验解读文档为准。
