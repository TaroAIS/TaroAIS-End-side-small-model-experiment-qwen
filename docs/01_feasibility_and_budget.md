# 01. 可行性与资源预算

## 推理后端
- 推荐：Ollama / llama.cpp server
- 当前主线：`Qwen3 4B`

## 核心约束
- 长文档任务不能依赖“大模型一次性吃完全部上下文”
- 需要通过协议与预算控制来平衡质量和时延

## 工程原则
- formal 主流程使用 real backend
- 默认保留 config snapshot、report 和 round snapshot
- 通过 `last_good_config` 保护回归
