# 06. Experiment Design And Ablation

## 主实验分组
- `baseline_rag`：单轮检索 + 直接回答。
- `edge_agent`：协议驱动迭代检索 + memory + early-stop/refine。

## 消融矩阵（固定必做）
- `iterative_off`：关闭迭代检索，只保留首轮检索。
- `fastpath_off`：关闭 single_doc fastpath（对应 `answer_type_policy.enable=false`）。
- `refine_gate_relaxed`：放宽 refine 门控，验证 forced_final 后 refine 的收益/代价。

## 扩展消融（可选）
- `query_rewrite_off`（multi_doc）
- `forced_retrieve_off`（single_doc/code）
- `entity_compact_off`（answer postprocess）

## 输出要求
每个消融必须产出：
- overall + 三任务 F1/EM
- P95 ratio、avg_steps、avg_retrieval、oom_count
- 样本级回归清单（至少 top5）

## 判定规则
- 任何消融导致单任务 F1 下降超过 0.03，记为关键机制。
- 若延迟显著下降但质量下降超过阈值，不作为主配置候选。
