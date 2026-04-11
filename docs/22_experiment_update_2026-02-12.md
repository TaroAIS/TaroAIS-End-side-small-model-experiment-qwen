# 22. 实验更新记录（2026-02-12）

## 1) 本次更新范围
- 完成了 `qwen3_small_reasoning_thesis_pack_v4` 的实验工程化落地：
  - 数据准备：`prepare -> index`
  - 主实验：`baseline -> agent -> evaluate`
  - 消融：按 `质量 / 成本 / 稳定性` 三组执行
  - Student 路线：`distill -> train_student -> eval_student`（独立分支）
- 所有主流程已提供 CLI，并由 Makefile 统一编排。

## 2) 数据集更新
- Smoke 数据：`smoke_data/minilongbench_tiny.jsonl`（3 条）
- 主评测数据接入：`scripts/prepare_longbench_3tasks.py` 支持远程下载 `zai-org/LongBench` 并生成 `LongBench_3tasks` canonical 集。
- 扩展训练池接入：`scripts/prepare_task_ext_corpus.py` 支持构建 `NarrativeQA/Qasper/HotpotQA/MuSiQue/RepoBench` 训练与验证集。
- 数据追溯文件：
  - `data/manifests/longbench_3tasks_source.json`
  - `data/manifests/dataset_registry.json`
  - `data/manifests/dataset_versions.json`

## 3) 本次已落地的数据状态
- 当前正式默认口径：
  - canonical：`data/main_eval/longbench_3tasks_test.jsonl`
  - dev：`data/main_eval/longbench_3tasks_dev100.jsonl`
  - holdout：`data/main_eval/longbench_3tasks_holdout100.jsonl`
  - train：`data/train_ext/combined_train.jsonl`
  - valid：`data/train_ext/combined_valid.jsonl`
- 所有新数据输出均要求通过 `schemas/dataset.schema.json` 校验。

## 4) 流程与产物
- Smoke 链路：`scripts/run_smoke.sh`
- 全流程链路：`make all`
- 典型产物：
  - 结果：`results/*.jsonl`
  - 报告：`report/metrics_table.csv`、`report/ablation_table.csv`、`report/*.png`
  - Student 评测：`report_student/student_controller_eval.csv`
  - 运行元信息：`results/run_*/metadata.json`

## 5) 命令脚本封装（新增）
- 新增目录：`scripts/cmd/`
- 每个流程步骤都有独立脚本，见 `scripts/cmd/README.md`：
  - `smoke.sh`
  - `prepare_remote.sh`
  - `prepare_remote_strict.sh`
  - `prepare_offline.sh`
  - `index.sh`
  - `baseline.sh`
  - `agent.sh`
  - `eval.sh`
  - `ablations.sh`
  - `distill.sh`
  - `train_student.sh`
  - `eval_student.sh`
  - `all.sh`

## 6) 兼容性说明
- 当前代码允许在无 GPU / 无 Ollama 场景下用 fallback 跑通流程。
- Student 训练默认是兼容型 placeholder 路径（确保流程可执行）。
- 如要真实训练与真实推理，请在有完整依赖和模型后端的环境运行。

## 7) 本次可信化优化（formal/smoke 分离）
- 新增 `run_mode` 贯穿主脚本：`smoke|formal`
  - `smoke`：允许 fallback/mock，仅用于链路验证
  - `formal`：禁止 mock，后端不可用直接失败
- 新增 `retrieval_scope`：`sample|global`，默认 `sample`
  - 主实验固定 `sample`（样本内检索）
  - `global` 保留为扩展实验
- 新增 `scripts/cmd/preflight_formal.sh`：
  - 检查 HF 数据可达、真实后端可达、`matplotlib/pandas` 可用
- `scripts/cmd/main_formal.sh` 作为 formal 主链：
  - `preflight -> prepare_remote_strict -> index -> baseline -> compare_controls -> agent -> eval -> ablations`
- `scripts/cmd/student_branch.sh` 作为独立 student 分支：
  - `distill -> train_student -> eval_student`
- `scripts/cmd/all.sh` 保留为兼容入口，等价于 `main_formal.sh`

## 8) 指标与元数据增强
- `result` 新增可选字段：
  - `backend_mode`（`real|mock|unknown`）
  - `prompt_tokens_total`
  - `completion_tokens_total`
  - `retrieved_chunks_total`
- `run_metadata` 新增可选字段：
  - `run_mode`
  - `dataset_source_meta_path`
- `report/metrics_table.csv` 新增成本列：
  - `avg_retrieved_chunks_total`
  - `avg_prompt_tokens_total`
  - `avg_completion_tokens_total`

## 9) 关键任务结论增强（多任务子集 + 95%CI + 门槛判定）
- `evaluate.py` 新增参数：
  - `--task_breakdown/--no_task_breakdown`
  - `--key_tasks`（默认 `multi_doc_qa code_qa`）
  - `--key_agg`（`macro|micro`，默认 `macro`）
  - `--run_tag`（用于 seed 标识）
- `evaluate.py` 新增产物：
  - `task_metrics.csv`（按任务）
  - `key_task_summary.csv`（关键任务聚合）
- 新增 `scripts/cmd/bench_key_tasks.sh`：
  - 默认 seeds：`42 123 2026`
  - 每个 seed 输出到 `report_key_supp/seed_<seed>/`
  - 自动汇总 `95%CI` 与门槛判定
- 新增 `scripts/aggregate_seed_runs.py`：
  - 输出：
    - `report_key_supp/seed_aggregate.csv`（mean/std/95%CI）
    - `report_key_supp/decision_gate.json`（pass/fail + reasons）
- 门槛默认值（中等严格）：
  - `delta_f1_key >= 0.03`
  - `latency_ratio <= 1.5`
  - `retrieval_ratio <= 1.8`

## 10) Student 关键任务对齐
- `scripts/eval_student_controller.py` 增加关键任务切片可选开关：
  - `--task_breakdown`
  - `--key_tasks`
  - `--key_agg`
- 新增 student 产物：
  - `report_student/student_task_metrics.csv`
  - `report_student/student_key_task_summary.csv`

## 11) 本次文档定位重构（从规范包到完整实验工程）
- 仓库主叙事已从“给 Codex 的规范包”切换为“可执行、可复现实验工程”。
- `README.md` 改为实验入口导航与结果解读入口。
- 新增 `docs/23_experiment_playbook.md` 作为实验解释主手册。
- `codex/` 保留但降级为历史附录，不再作为主入口。

## 12) 结果快照解释规则
- `smoke` 快照：
  - 仅用于链路可执行性、schema/格式正确性、报告产物完整性验证。
  - 不进入论文主结论。
- `formal` 快照：
  - 仅在真实后端 + 严格失败语义下产生。
  - 结合 `retrieval_scope=sample` 与多 seed 结果，作为论文主表依据。
- 主结论最低约束：
  - `run_mode=formal`
  - `retrieval_scope=sample`
  - `canonical` 三任务门槛 + `3-seed/CI`
  - 关键任务 benchmark 仅作补充证据。

## 13) 关键任务门槛判定解释样例（decision_gate.json）
- 文件：`report_key_supp/decision_gate.json`
- 关键字段语义：
  - `pass`：是否通过最终门槛
  - `thresholds`：门槛定义
  - `observed`：当前聚合统计下的观测值
  - `checks`：每一项门槛的通过/失败
  - `fail_reasons`：失败原因列表（便于答辩与排障）

示例解释（当前 smoke 快照）：
- `pass=false`，表示当前关键任务结论未达标。
- 若 `delta_f1_pass=false`：说明效果增益不足。
- 若 `latency_ratio_pass=false`：说明延迟成本超过门槛。
- 若 `retrieval_ratio_pass=false`：说明检索成本超过门槛。
- 该样例用于验证判定器行为，不用于 formal 主结论。
