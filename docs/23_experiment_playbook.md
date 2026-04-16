# 23. Experiment Playbook

## 1. 研究目标
主实验固定回答一个问题：
- 在 `Qwen3 4B` 条件下，`edge_agent_4b` 能否在 `LongBench_3tasks canonical` 上，相对强对照实现三任务平衡提升，并同时满足时延与稳定性门槛。

## 2. 论文主张
- 不是“大模型更强”，而是“小模型长上下文失败模式具有任务异质性”。
- 不是“通用 agent”，而是“`budget-aware task-routed protocol for 4B long-context reasoning`”。
- 不是“只做亮点分数”，而是“主结论看 canonical，亮点任务看 `code_qa`，效率路线看 student”。

## 3. 数据角色
- `canonical`
  - 路径：`data/main_eval/longbench_3tasks_test.jsonl`
  - 作用：唯一论文主结论
- `monitor_dev_cross_source`
  - 路径：`data/main_eval/longbench_3tasks_dev100.jsonl`
  - 作用：高频调参与早期风险暴露
- `monitor_holdout_cross_source`
  - 路径：`data/main_eval/longbench_3tasks_holdout100.jsonl`
  - 作用：跨来源风险复核
- `quickgate30`
  - 路径：`data/main_eval/longbench_3tasks_quickgate30.jsonl`
  - 作用：晋级预筛
- `code_generalization_appendix`
  - 路径：`data/main_eval/code_generalization/code_generalization_appendix.jsonl`
  - 作用：补充 `code_qa` 外部效度，不替代 canonical

## 4. 正式主流程
- `baseline_rag_4b`
- `baseline_budget_matched_4b`
- `baseline_single_round_strong_4b`
- `edge_agent_4b`
- `canonical` 单 seed
- `canonical` 连续两轮通过后执行 `3-seed confirm`
- 通过后冻结主配置，再进入 `student_branch`

## 5. 轮次策略
- Round 0
  - 只做 `canonical calibration`
  - 固定四路对照与当前主 agent
  - 产出门槛来源与 paper-ready 目标带
- Round 1+
  - 每轮先跑 `dev100 + holdout100 + quickgate30`
  - 三者同时通过晋级条件后，才进入 `canonical`
  - 每轮只允许修改一个主因子
  - 连续两轮 `canonical` 无显著提升则停止调参
- Freeze
  - `canonical` 连续两轮通过后，执行 `3-seed = 42 / 123 / 2026`
  - `3-seed + CI` 通过后冻结主配置

## 6. 对照组
- `baseline_rag`
  - 标准单轮检索回答
- `baseline_budget_matched`
  - 回答“收益是否只是多花预算”
- `baseline_single_round_strong`
  - 回答“收益是否只是单轮检索更强”
- `edge_agent`
  - 任务路由式协议、迭代检索、fact memory、budget guard、early-stop、refine gate

## 7. 消融
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

## 8. Student
- student 不在 formal 主结论链路内
- 只有 canonical 主配置冻结后才运行
- 执行顺序固定：
  - `holdout100`
  - `canonical`
- student 只提供效率路线补充证据，不参与主结论通过判定

## 9. 论文引用规则
- 主文主表：只引用 canonical
- `dev100 / holdout100 / quickgate30`：只引用为“迭代与晋级证据”
- `code_qa` 大幅提升：只引用为亮点任务证据
- `student`：只引用为压缩与效率补充证据
- 历史快照与旧轮次：只放附录，不进入正文主论证
