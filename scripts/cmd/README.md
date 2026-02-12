# scripts/cmd

每个脚本对应一个固定流程命令，方便直接执行。

## 通用约定
- 默认使用 `python3`
- 默认 `RUN_MODE=formal`、`RETRIEVAL_SCOPE=sample`
- 可通过环境变量覆盖：
  - `PYTHON_BIN=python3.10 bash scripts/cmd/smoke.sh`
  - `RUN_MODE=smoke RETRIEVAL_SCOPE=sample bash scripts/cmd/baseline.sh`

## Smoke 与 Formal
- `smoke`：允许 fallback/mock，用于链路快速验证。
- `formal`：严格模式，要求真实后端与真实图表依赖，不允许 mock 结果混入主报告。

## 脚本清单（含证据类型）
- `bash scripts/cmd/preflight_formal.sh`
  - 作用：formal 预检（远程数据可达、真实后端可用、绘图依赖可用）。
  - 证据类型：`formal 主结论前置门禁`

- `bash scripts/cmd/smoke.sh`
  - 作用：运行 smoke 全链路（baseline + agent + evaluate，`RUN_MODE=smoke`）。
  - 证据类型：`smoke 验证`

- `bash scripts/cmd/prepare_remote.sh`
  - 作用：下载/准备正式 MiniLongBench（远程优先，失败可回退）。
  - 证据类型：`数据准备（非主结论）`

- `bash scripts/cmd/prepare_remote_strict.sh`
  - 作用：下载/准备正式 MiniLongBench（严格远程，失败直接报错）。
  - 证据类型：`formal 主结论前置数据`

- `bash scripts/cmd/prepare_offline.sh`
  - 作用：仅用 smoke 数据扩展生成 train/valid/test。
  - 证据类型：`smoke 验证`

- `bash scripts/cmd/index.sh`
  - 作用：构建 chunk 与检索索引。
  - 证据类型：`formal 主结论 / 扩展实验`

- `bash scripts/cmd/baseline.sh`
  - 作用：运行 baseline RAG（默认 formal + sample 检索）。
  - 证据类型：`formal 主结论核心对比`

- `bash scripts/cmd/agent.sh`
  - 作用：运行 edge agent（默认 formal + sample 检索）。
  - 证据类型：`formal 主结论核心对比`

- `bash scripts/cmd/eval.sh`
  - 作用：生成主报告。
  - 证据类型：`formal 主结论指标与图表`

- `bash scripts/cmd/ablations.sh`
  - 作用：运行四组消融并更新报告。
  - 证据类型：`扩展实验（机制归因）`

- `bash scripts/cmd/distill.sh`
  - 作用：蒸馏 student 控制器训练数据。
  - 证据类型：`student 路线`

- `bash scripts/cmd/train_student.sh`
  - 作用：训练 student（formal 下自动加 `--prefer_real`）。
  - 证据类型：`student 路线`

- `bash scripts/cmd/eval_student.sh`
  - 作用：student 控制器行为 + 端到端评测。
  - 证据类型：`student 路线结论`

- `bash scripts/cmd/bench_key_tasks.sh`
  - 作用：多 seed 关键任务评测（`multi_doc_qa+code_qa`）并输出 `95%CI` 与门槛判定。
  - 证据类型：`formal 主结论（关键任务）`

- `bash scripts/cmd/all.sh`
  - 作用：formal 全链路：`preflight -> prepare(strict) -> index -> baseline -> agent -> eval -> ablations -> distill -> train -> eval_student`。
  - 证据类型：`总编排（主结论+扩展+student）`

## 推荐执行序列（工程视角）
1. `bash scripts/cmd/smoke.sh`
2. `bash scripts/cmd/preflight_formal.sh`
3. `bash scripts/cmd/all.sh`
4. 需要关键任务统计时：`bash scripts/cmd/bench_key_tasks.sh`

## 推荐执行序列（论文结论视角）
1. `bash scripts/cmd/preflight_formal.sh`
2. `RUN_MODE=formal RETRIEVAL_SCOPE=sample bash scripts/cmd/bench_key_tasks.sh`
3. 查看 `report_key/seed_aggregate.csv` 与 `report_key/decision_gate.json`
4. 再补充 `bash scripts/cmd/ablations.sh` 与 `bash scripts/cmd/eval_student.sh` 作为扩展证据
