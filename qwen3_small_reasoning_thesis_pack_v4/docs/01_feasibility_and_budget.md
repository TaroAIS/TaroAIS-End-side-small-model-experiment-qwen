# 01. 可行性与资源预算（4060 8GB 专用）

## 推理后端选择
- 推荐：Ollama / llama.cpp server（OpenAI-compatible API）用于端侧 8B GGUF
- HF Transformers：主要用于训练 Student/评测小模型

## 关键参数（建议写进 metadata.json）
- n_ctx（8192/12288）
- n_gpu_layers（尽可能高，剩余走 CPU）
- quantization（例如 gguf-q4_k_m）

## 风险与规避
- OOM：必须执行 token budget + prune（详见 docs/03_agent_algorithm.md）
- 慢：限制 max_steps<=6，开启 embedding cache
- 不可复现：保存 config snapshot + metadata.json（schemas/run_metadata.schema.json）
