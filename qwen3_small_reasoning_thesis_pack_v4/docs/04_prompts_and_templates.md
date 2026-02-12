# 04. Prompt 模板（统一管理）

包含：
- Agent system prompt（协议强约束）
- Baseline RAG prompt（非 thinking）
- 格式纠错 prompt（protocol repair）
- facts 抽取 prompt（可选）

要求：
- 所有 prompt 由 agent/prompts.py 统一加载，禁止散落在代码里
