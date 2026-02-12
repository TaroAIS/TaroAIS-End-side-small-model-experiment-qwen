# 19. Student-Controller 专用评测（让“训练小模型”像成果）

## 19.1 两类评测
A) 控制器行为评测（不跑大模型也能评）
- 给定 (question + ctx摘要)，Student 输出 <search> 或 <final>
- 指标：
  - trigger_acc（该 search 时 search 的准确率）
  - macro-F1（search vs final 分类）
  - keyword_hit_rate：用输出 keyword 检索 Top-1 是否命中 gold evidence（近似指标）

B) 端到端评测（接入 Agent）
- 用 Student 代替 Teacher 做“检索控制器”，推理端仍用 Qwen3-8B
- 比较：
  - 任务 F1
  - avg_retrieval
  - latency

## 19.2 评测集构建建议
- 从训练数据中留出 eval split（10~20%）
- 保证 multi_doc_qa 占比足够（更能体现控制策略）
