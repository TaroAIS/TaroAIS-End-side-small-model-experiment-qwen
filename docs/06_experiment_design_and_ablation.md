# 06. Experiment Design And Ablation

## 主对照
- `baseline_rag`
- `baseline_budget_matched`
- `baseline_single_round_strong`
- `edge_agent`

## 消融分组
### 质量来源
- `iterative_off`
- `memory_sliding`
- `refine_gate_relaxed`

### 成本来源
- `budget_tight`
- `topk_tight`
- `max_steps_2`

### 稳定性来源
- `forced_retrieve_off`
- `early_stop_off`
- `promotion_guard_off`

## 输出要求
每个消融至少报告：
- overall F1
- `single_doc_qa / multi_doc_qa / code_qa` F1
- `P95 ratio`
- `avg_steps`
- `avg_retrieval`
- `oom_count`

## 判定规则
- 单任务 F1 下降超过 `0.03`，视为关键机制
- 如果成本下降但质量明显回撤，不作为主配置候选
- 如果稳定性消融显著放大尾延迟或跨轮波动，记为稳定性关键机制
