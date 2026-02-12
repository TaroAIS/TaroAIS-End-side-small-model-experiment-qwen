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

## 脚本清单
- `bash scripts/cmd/preflight_formal.sh`
  - formal 预检：远程数据可达、真实后端可用、绘图依赖可用。
- `bash scripts/cmd/smoke.sh`
  - 运行 smoke 全链路（baseline + agent + evaluate，`RUN_MODE=smoke`）。
- `bash scripts/cmd/prepare_remote.sh`
  - 下载/准备正式 MiniLongBench（远程优先，失败可回退）。
- `bash scripts/cmd/prepare_remote_strict.sh`
  - 下载/准备正式 MiniLongBench（严格远程，失败直接报错）。
- `bash scripts/cmd/prepare_offline.sh`
  - 仅用 smoke 数据扩展生成 train/valid/test。
- `bash scripts/cmd/index.sh`
  - 构建 chunk 与检索索引。
- `bash scripts/cmd/baseline.sh`
  - 运行 baseline RAG（默认 formal + sample 检索）。
- `bash scripts/cmd/agent.sh`
  - 运行 edge agent（默认 formal + sample 检索）。
- `bash scripts/cmd/eval.sh`
  - 生成主报告。
- `bash scripts/cmd/ablations.sh`
  - 运行四组消融并更新报告。
- `bash scripts/cmd/distill.sh`
  - 蒸馏 student 控制器训练数据。
- `bash scripts/cmd/train_student.sh`
  - 训练 student（formal 下自动加 `--prefer_real`）。
- `bash scripts/cmd/eval_student.sh`
  - student 控制器行为 + 端到端评测。
- `bash scripts/cmd/bench_key_tasks.sh`
  - 多 seed 关键任务评测（`multi_doc_qa+code_qa`）并输出 `95%CI` 与门槛判定。
- `bash scripts/cmd/all.sh`
  - formal 全链路：`preflight -> prepare(strict) -> index -> baseline -> agent -> eval -> ablations -> distill -> train -> eval_student`。
