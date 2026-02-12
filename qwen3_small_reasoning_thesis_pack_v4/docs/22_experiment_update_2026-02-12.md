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
