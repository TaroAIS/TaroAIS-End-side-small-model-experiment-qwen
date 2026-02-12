# 15. 成本口径（必须写清楚，否则曲线没意义）

## 15.1 延迟
- total = llm + retrieval + overhead
- llm：仅 LLM 生成耗时
- retrieval：embedding/search/IO 之和
- 统计：P50/P95（单位 ms）

## 15.2 检索成本
- n_retrieval：每轮 <search> 触发次数
- retrieved_chunks：实际加入 prompt 的 chunk 数
- tokens：
  - prompt_tokens（每轮）
  - total_prompt_tokens（全程）
  - completion_tokens（全程）

## 15.3 显存成本
- peak GPU mem（MB）：NVML time series 的最大值
- mean GPU mem：均值
- series：可选保存，用于画曲线

## 15.4 成本-效果曲线的解释建议
- x 轴可选：P95 latency / avg_retrieval / total_prompt_tokens
- y 轴：F1
- 重点讲 Pareto 改善：同成本更高 F1 或同 F1 更低成本
