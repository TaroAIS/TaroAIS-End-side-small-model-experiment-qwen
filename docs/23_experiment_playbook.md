# 23. Experiment Playbook（Canonical 三任务平衡）

## 1. 研究问题
主结论口径统一为三任务平衡，而不是“关键任务优先”单点优化。
- single_doc_qa：验证短链路与事实抽取质量。
- multi_doc_qa：验证多跳检索与证据融合能力。
- code_qa：验证代码语义检索与精确回答能力。

## 2. 主实验定义（Main Track）
- 数据：`data/minilongbench_test.jsonl`
- 对照：`baseline_rag` vs `edge_agent`
- 运行：formal + sample
- 统计：单 seed 迭代，周期性 3-seed（42/123/2026）复核

## 3. 验收门槛
- 单 seed（canonical）：
  - `overall F1 >= 0.37`
  - `single_doc_qa F1 >= 0.29`
  - `P95 ratio <= 1.8`
  - `oom_count = 0`
- 3-seed（canonical）：
  - `mean overall F1 >= 0.37`
  - `mean single_doc_qa F1 >= 0.29`
  - `mean P95 ratio <= 1.8`
  - `all oom_count = 0`
- 显著性：三任务 seed-level `delta_F1` 至少 2/3 的 95%CI 下界 > 0。

## 4. 扩展实验（Extended Track）
- 数据：`dev100` 与 `holdout100`
- 作用：泛化监测与风险预警，不反向主导主实验调参。

## 5. 消融实验（Ablation Track）
固定必做三项：
- `iterative_off`
- `fastpath_off`
- `refine_gate_relaxed`

目的：验证 single_doc 回归是机制组合问题，而非随机波动。

## 6. 样本级分析输出
每轮必须输出：
- `regression_top`
- `improvement_top`
- `latency_top`
- 机制标签分布（forced_final/fastpath/refine_skip_reason/forced_search）

## 7. 结果使用规则
- 论文主结论只引用 Main Track 的稳定通过结果。
- Extended/Ablation 作为证据补充与机制解释，不替代主结论门槛。
