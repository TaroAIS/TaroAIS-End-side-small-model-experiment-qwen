# 23. Experiment Playbook（Canonical 三任务平衡）

## 1. 研究问题
主结论口径统一为三任务平衡，而不是“关键任务优先”单点优化。
- single_doc_qa：验证短链路与事实抽取质量。
- multi_doc_qa：验证多跳检索与证据融合能力。
- code_qa：验证代码语义检索与精确回答能力。

## 2. 主实验定义（Main Track）
- 数据：`data/main_eval/longbench_3tasks_test.jsonl`
- 对照：`baseline_rag` / `baseline_budget_matched` / `baseline_single_round_strong` / `edge_agent`
- 运行：formal + sample
- 统计：单 seed 迭代，周期性 3-seed（42/123/2026）复核
- 主胜负口径：canonical 三任务门槛 + 3-seed + CI

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
- 数据：`data/main_eval/longbench_3tasks_dev100.jsonl` 与 `data/main_eval/longbench_3tasks_holdout100.jsonl`
- 作用：跨来源风险预警，不反向主导主实验调参。
- 命名语义：
  - `monitor_dev_cross_source`
  - `monitor_holdout_cross_source`

## 5. 消融实验（Ablation Track）
固定分三组：
- 质量：`iterative_off` / `memory_sliding` / `refine_gate_relaxed`
- 成本：`budget_tight`
- 稳定性：`forced_retrieve_off` / `early_stop_off`

目的：围绕质量、尾延迟和跨 seed 稳定性三类失败模式做归因。

## 6. 门槛标定（Calibration Phase）
- 在正式冻结论文门槛前，运行 `bash scripts/cmd/calibrate_thresholds.sh`
- 比较：
  - `baseline_rag`
  - `baseline_budget_matched`
  - `baseline_single_round_strong`
  - `edge_agent`
  - 代表性 agent 变体
- 当前阈值冻结记录：`data/manifests/threshold_calibration_policy.json`

## 7. 样本级分析输出
每轮必须输出：
- `regression_top`
- `improvement_top`
- `latency_top`
- 机制标签分布（forced_final/fastpath/refine_skip_reason/forced_search）

## 8. 结果使用规则
- 论文主结论只引用 Main Track 的稳定通过结果。
- Extended/Ablation 作为证据补充与机制解释，不替代主结论门槛。
- student 结果只作为效率路线补充证据，不纳入主实验默认通过条件。
