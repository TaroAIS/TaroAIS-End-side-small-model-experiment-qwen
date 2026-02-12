# 21. 神经符号接口（可选加分）

你可以把 fact_memory 的 facts 进一步结构化为：
- entity / relation / constraint
并用简单规则做一致性检查（例如互斥、数值范围、依赖关系），再把结果反馈给 LLM。

最小实现（不影响毕业）：
- 仅做 facts JSON 输出 + 一条规则：若同一实体出现冲突数值，标记为 inconsistency 并提示模型再 search。
