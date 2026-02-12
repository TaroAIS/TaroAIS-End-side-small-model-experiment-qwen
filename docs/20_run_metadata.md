# 20. Run Metadata（强制可复现）

## 20.1 为什么要写 metadata.json
答辩最常被问：你这次结果是在什么参数下跑的？量化方式？上下文多大？

## 20.2 必须写入的字段（schema=schemas/run_metadata.schema.json）
- run_id、timestamp_utc、git_commit
- config_paths（保存使用过的 configs）
- model_info：backend/name_or_path/quantization/n_ctx/n_gpu_layers
- hardware：gpu_name/gpu_mem_mb/cpu/ram_gb
- seeds：python/numpy/torch

## 20.3 建议做法
- run_agent.py 与 run_baseline_rag.py 启动时就创建 run 目录：
  - results/run_{timestamp}/
  - 写入 metadata.json
  - 拷贝 config snapshot
