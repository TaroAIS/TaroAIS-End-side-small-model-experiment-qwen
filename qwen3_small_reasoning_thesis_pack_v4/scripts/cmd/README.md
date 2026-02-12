# scripts/cmd

每个脚本对应一个固定流程命令，方便直接执行。

## 通用约定
- 默认使用 `python3`
- 可通过环境变量覆盖：
  - `PYTHON_BIN=python3.10 bash scripts/cmd/prepare_remote.sh`

## 脚本清单
- `bash scripts/cmd/smoke.sh`
  - 运行 smoke 全链路（baseline + agent + evaluate）
- `bash scripts/cmd/prepare_remote.sh`
  - 下载/准备正式 MiniLongBench（远程优先，失败可回退）
- `bash scripts/cmd/prepare_remote_strict.sh`
  - 下载/准备正式 MiniLongBench（严格远程，失败直接报错）
- `bash scripts/cmd/prepare_offline.sh`
  - 仅用 smoke 数据扩展生成 train/valid/test
- `bash scripts/cmd/index.sh`
  - 构建 chunk 与检索索引
- `bash scripts/cmd/baseline.sh`
  - 运行 baseline RAG
- `bash scripts/cmd/agent.sh`
  - 运行 edge agent
- `bash scripts/cmd/eval.sh`
  - 生成主报告
- `bash scripts/cmd/ablations.sh`
  - 运行四组消融并更新报告
- `bash scripts/cmd/distill.sh`
  - 蒸馏 student 控制器训练数据
- `bash scripts/cmd/train_student.sh`
  - 训练 student（当前为兼容型训练入口）
- `bash scripts/cmd/eval_student.sh`
  - student 控制器行为+端到端评测
- `bash scripts/cmd/all.sh`
  - 串行执行 prepare/index/baseline/agent/eval/ablations/distill/train/eval_student
