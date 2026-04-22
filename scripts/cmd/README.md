# scripts/cmd 命令入口说明

本目录放的是推荐直接执行的实验入口脚本。默认主线已经统一到：

- 模型：`qwen3:4b`
- 主评测：`LongBench_3tasks canonical`
- 主流程：`prepare -> index -> baseline -> compare_controls -> agent -> eval -> ablations -> bench_key_tasks`

## 1. 通用约定

- 默认 Python：`python3` 或 `_common.sh` 中的 `PYTHON_BIN`
- 默认运行模式：`RUN_MODE=formal`
- 默认检索范围：`RETRIEVAL_SCOPE=sample`
- smoke 模式只使用：`smoke_data/minilongbench_tiny.jsonl`

## 2. 默认数据路径

- canonical：`data/main_eval/longbench_3tasks_test.jsonl`
- dev100：`data/main_eval/longbench_3tasks_dev100.jsonl`
- holdout100：`data/main_eval/longbench_3tasks_holdout100.jsonl`
- quickgate30：`data/main_eval/longbench_3tasks_quickgate30.jsonl`
- train：`data/train_ext/combined_train.jsonl`
- valid：`data/train_ext/combined_valid.jsonl`

## 3. 核心脚本

### `smoke.sh`

```bash
bash scripts/cmd/smoke.sh
```

用途：

- 最小链路检查。

### `prepare_remote_strict.sh`

```bash
bash scripts/cmd/prepare_remote_strict.sh
```

用途：

- 生成主评测集、扩展训练池和监测集。

### `index.sh`

```bash
bash scripts/cmd/index.sh
```

用途：

- 从 `data/train_ext/combined_train.jsonl` 构建检索索引。

### `baseline.sh`

```bash
bash scripts/cmd/baseline.sh
```

用途：

- 运行 anchor baseline。

### `compare_controls.sh`

```bash
bash scripts/cmd/compare_controls.sh
```

用途：

- 运行两个强对照：
  - `baseline_budget_matched`
  - `baseline_single_round_strong`

### `agent.sh`

```bash
bash scripts/cmd/agent.sh
```

用途：

- 运行正式 agent 配置。

### `eval.sh`

```bash
bash scripts/cmd/eval.sh
```

用途：

- 生成 `metrics_table.csv`、`task_metrics.csv`、`key_task_summary.csv`、`error_cases.jsonl`
- 自动尝试渲染论文科研图到 `report/paper_figures/`

### `ablations.sh`

```bash
bash scripts/cmd/ablations.sh
```

用途：

- 运行质量、成本、稳定性三组消融。

### `bench_key_tasks.sh`

```bash
bash scripts/cmd/bench_key_tasks.sh
```

用途：

- canonical 上执行多种子确认。
- 默认汇总三类任务，不再只看 `multi_doc_qa + code_qa`。

### `main_formal.sh`

```bash
bash scripts/cmd/main_formal.sh
```

用途：

- 一键跑正式主流程。

执行顺序：

1. `preflight_formal.sh`
2. `prepare_remote_strict.sh`
3. `index.sh`
4. `baseline.sh`
5. `compare_controls.sh`
6. `agent.sh`
7. `eval.sh`
8. `ablations.sh`
9. `bench_key_tasks.sh`

## 4. 附加脚本

### `student_branch.sh`

```bash
bash scripts/cmd/student_branch.sh
```

用途：

- 冻结主配置之后运行 student 路线。

### `render_paper_figures.sh`

```bash
bash scripts/cmd/render_paper_figures.sh
```

用途：

- 从已有 report 目录直接生成论文图，不重跑实验。

## 5. 推荐执行顺序

1. `bash scripts/cmd/smoke.sh`
2. `bash scripts/cmd/prepare_remote_strict.sh`
3. `bash scripts/cmd/index.sh`
4. `bash scripts/cmd/main_formal.sh`
5. 如需复用已有结果出图：`bash scripts/cmd/render_paper_figures.sh`
6. 如需 student 路线：`bash scripts/cmd/student_branch.sh`
