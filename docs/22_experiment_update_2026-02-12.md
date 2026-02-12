# 22. 实验更新记录（2026-02-12）

## 1) 本次更新范围
- 完成了 `qwen3_small_reasoning_thesis_pack_v4` 的实验工程化落地：
  - 数据准备：`prepare -> index`
  - 主实验：`baseline -> agent -> evaluate`
  - 消融：`think_off / iterative_off / memory_sliding / inj_defense_off`
  - Student 路线：`distill -> train_student -> eval_student`
- 所有主流程已提供 CLI，并由 Makefile 统一编排。

## 2) 数据集更新
- Smoke 数据：`smoke_data/minilongbench_tiny.jsonl`（3 条）
- 正式数据接入：`scripts/prepare_minilongbench.py` 支持远程下载 MiniLongBench（HF: `linggm/MiniLongBench`）并转换到本项目 schema。
- 版本固定：默认 revision `0ba7bf46265f1f783653693fb6b581f617f37275`。
- 数据追溯文件：`data/minilongbench_source.json`。

## 3) 本次已落地的数据状态
- 当前正式数据切分（remote strict）:
  - `data/minilongbench_train.jsonl`: 183
  - `data/minilongbench_valid.jsonl`: 28
  - `data/minilongbench_test.jsonl`: 26
  - 合计：237
- 三个 split 均通过 `schemas/dataset.schema.json` 校验。

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
- `scripts/cmd/all.sh` 调整为 formal 严格链路：
  - `preflight -> prepare_remote_strict -> index -> baseline -> agent -> eval -> ablations -> distill -> train_student -> eval_student`

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
  - 每个 seed 输出到 `report_key/seed_<seed>/`
  - 自动汇总 `95%CI` 与门槛判定
- 新增 `scripts/aggregate_seed_runs.py`：
  - 输出：
    - `report_key/seed_aggregate.csv`（mean/std/95%CI）
    - `report_key/decision_gate.json`（pass/fail + reasons）
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
