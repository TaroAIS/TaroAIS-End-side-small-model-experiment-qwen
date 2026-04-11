# Qwen3 端侧推理 + 小模型蒸馏 完整实验工程

更新日期：2026-02-12

本仓库已经从模板阶段升级为可执行、可复现实验工程，目标是验证：
- 在 `LongBench_3tasks canonical` 上，`edge_agent` 是否相对 `baseline_rag` 实现三任务平衡提升；
- 同时满足“代价可接受”的成本门槛（延迟/检索开销）与多 seed 稳定性门槛。

## 当前仓库状态
- 主实验主链：`prepare -> index -> baseline -> compare_controls -> agent -> evaluate -> ablations`
- Student 分支：`distill -> train_student -> eval_student`
- 对照组：`baseline_rag` / `baseline_budget_matched` / `baseline_single_round_strong` / `edge_agent`
- 消融：按 `质量 / 成本 / 稳定性` 三组组织
- 补充 benchmark：关键任务多 seed 统计（`report_key_supp/`），不作为主胜负口径

## 快速开始（工程运行）
1) 先跑 smoke（链路验证，允许 fallback/mock）：
- `bash scripts/cmd/smoke.sh`

2) 再跑 formal 主实验（论文主结论入口，严格失败语义）：
- `bash scripts/cmd/main_formal.sh`

3) 如需 student 分支：
- `bash scripts/cmd/student_branch.sh`

4) 如需关键任务补充 benchmark（默认 42/123/2026）：
- `bash scripts/cmd/bench_key_tasks.sh`

5) 如需门槛标定实验：
- `bash scripts/cmd/calibrate_thresholds.sh`

脚本文档：`scripts/cmd/README.md`

## 实验视角总览
- 主对比：`baseline_rag` vs `baseline_budget_matched` vs `baseline_single_round_strong` vs `edge_agent`
- 主实验口径：`run_mode=formal` + `retrieval_scope=sample`
- `global` 检索范围仅用于扩展实验，不混入主表
- 主结论口径：canonical 三任务门槛 + 多 seed + CI
- 关键任务聚合默认：`key_tasks=multi_doc_qa code_qa` + `key_agg=macro`，仅作补充收益-成本对照

## 结果如何读
主结论建议读取顺序：
1) `report/metrics_table.csv`
2) `report/task_metrics.csv`
3) `docs/14_metrics_definition.md`

补充 benchmark 读取顺序：
1) `report_key_supp/decision_gate.json`
2) `report_key_supp/seed_aggregate.csv`
3) `report_key_supp/seed_<n>/key_task_summary.csv`

## 当前结果快照说明（2026-02-12）
- 当前仓库包含已运行产物快照（`report_tiny/`、`report_key_supp/`、`results/run_*`）。
- 这些快照会随复跑变化，不应当作固定真值。
- `report_key_supp` 当前快照来自补充 benchmark 或历史链路验证，不直接代表 canonical 主结论：
  - `delta_f1_key_mean = -0.0625`
  - `latency_ratio_key_mean = 3.6258`
  - `retrieval_ratio_key_mean = 3.5`
- 只有 `main_formal + canonical + multi-seed + CI` 的结果才用于论文主结论。

## 数据来源与版本
### Smoke 数据
- `smoke_data/minilongbench_tiny.jsonl`
- 3 条样本：`single_doc_qa` / `multi_doc_qa` / `code_qa`

### 正式主评测
- 主评测来源：Hugging Face `zai-org/LongBench`
- 输出路径：`data/main_eval/longbench_3tasks_test.jsonl`
- 仅保留三类任务：
  - `single_doc_qa`: `narrativeqa/qasper/multifieldqa_en/multifieldqa_zh`
  - `multi_doc_qa`: `hotpotqa/2wikimqa/musique/dureader`
  - `code_qa`: `lcc/repobench-p`
- 来源追溯：`data/manifests/longbench_3tasks_source.json`

### 扩展训练池
- `single_doc_qa`: `NarrativeQA + Qasper`
- `multi_doc_qa`: `HotpotQA + MuSiQue`
- `code_qa`: `RepoBench v1.1 (Python + Java)`
- 合并输出：
  - `data/train_ext/combined_train.jsonl`
  - `data/train_ext/combined_valid.jsonl`
- 版本与注册清单：
  - `data/manifests/dataset_registry.json`
  - `data/manifests/dataset_versions.json`

## 文档入口
- 实验主手册：`docs/23_experiment_playbook.md`
- 消融与对照：`docs/06_experiment_design_and_ablation.md`
- 门槛与标定：`docs/14_metrics_definition.md`
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
