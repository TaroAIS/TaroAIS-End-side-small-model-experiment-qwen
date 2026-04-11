# 06. Experiment Design And Ablation

## 主实验分组
- `baseline_rag`：默认单轮检索 + 直接回答。
- `baseline_budget_matched`：预算匹配的单轮控制基线。
- `baseline_single_round_strong`：更强检索与更长解码的单轮控制基线。
- `edge_agent`：协议驱动迭代检索 + memory + early-stop/refine。

## 消融矩阵（固定必做）
### 质量来源
- `iterative_off`：关闭迭代检索，只保留首轮检索。
- `memory_sliding`：把事实记忆改为滑窗记忆，验证信息保真度影响。
- `refine_gate_relaxed`：放宽 refine 门控，验证 forced_final 后 refine 的收益/代价。

### 成本来源
- `budget_tight`：收紧检索预算、步数和解码上限，验证尾延迟来源。

### 稳定性来源
- `forced_retrieve_off`：关闭补检索触发，验证单轮漂移与漏证据风险。
- `early_stop_off`：关闭早停策略，验证长尾与跨 seed 波动风险。

## 输出要求
每个消融必须产出：
- overall + 三任务 F1/EM
- P95 ratio、avg_steps、avg_retrieval、oom_count
- 样本级回归清单（至少 top5）

## 判定规则
- 任何消融导致单任务 F1 下降超过 0.03，记为关键机制。
- 若延迟显著下降但质量下降超过阈值，不作为主配置候选。
- 若稳定性消融显著放大 `P95 ratio` 或 seed 间波动，记为稳定性关键机制。
