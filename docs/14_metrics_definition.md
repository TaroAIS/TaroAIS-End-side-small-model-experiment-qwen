# 14. Metrics Definition

## 14.1 基础指标
- `EM`
  - 标准化后严格匹配
- `F1`
  - 主质量指标
- `single_doc_qa / multi_doc_qa / code_qa F1`
  - 三任务分项指标
- `P95 latency`
  - 样本级尾延迟
- `P95 ratio`
  - `agent / baseline_rag` 的尾延迟比值
- `avg_steps`
  - 平均推理步数
- `avg_retrieval`
  - 平均检索次数
- `oom_count`
  - 运行失败代理指标

## 14.2 4B canonical 主门槛
当前主门槛由 [threshold_calibration_policy.json](/d:/taroPROJECT/end%20design/TaroAIS-End-side-small-model-experiment-qwen/data/manifests/threshold_calibration_policy.json) 管理。

### 单 seed
- `overall F1 >= 0.34`
- `single_doc_qa F1 >= 0.29`
- `P95 ratio <= 1.80`
- `oom_count = 0`

### 3-seed
- `mean overall F1 >= 0.34`
- `mean single_doc_qa F1 >= 0.29`
- `mean P95 ratio <= 1.80`
- `all seeds oom_count = 0`

## 14.3 监测集门槛
### dev100
- `overall F1 >= 0.31`
- `single_doc_qa F1 >= 0.27`
- `P95 ratio <= 1.95`

### holdout100
- `overall F1 >= 0.32`
- `single_doc_qa F1 >= 0.28`
- `P95 ratio <= 1.90`

### quickgate30
- `overall F1 >= 0.32`
- `single_doc_qa F1 >= 0.28`
- `P95 ratio <= 1.80`

说明：
- `dev100 / holdout100 / quickgate30` 只负责晋级与风险监测，不替代 canonical 主结论。

## 14.4 校准来源
- 校准入口：`bash scripts/cmd/calibrate_thresholds.sh`
- 校准数据：`data/main_eval/longbench_3tasks_test.jsonl`
- 最低比较集合：
  - `baseline_rag`
  - `baseline_budget_matched`
  - `baseline_single_round_strong`
  - `edge_agent`
  - 至少两个代表性 agent 变体
- 当前阈值定位：
  - 仍属于 `provisional_frozen_policy`
  - 不是历史大模型常数
  - 后续若更换模型、后端、索引策略或主数据，需要重新校准

## 14.5 Paper-Ready 目标带
这些目标不是 formal gate，而是论文写作目标。

### Canonical 主结论目标
- overall F1：相对 `baseline_rag_4b` 提升 `+0.015` 到 `+0.030`
- `single_doc_qa`：至少非负提升，目标 `+0.010` 以上
- `multi_doc_qa`：目标 `+0.020` 以上
- `code_qa`：目标 `+0.030` 以上
- `P95 ratio <= 1.75`
- `OOM = 0`

### 亮点任务目标
- 在 `holdout100` 或 `quickgate30` 上，`code_qa` 相对 baseline 提升 `+0.20` 以上
- 该目标只用于亮点叙事，不替代 canonical 主结论

## 14.6 显著性与稳定性
- canonical 冻结后执行 `3-seed = 42 / 123 / 2026`
- 统一报告：
  - `mean`
  - `std`
  - 必要时补 `95% CI`
- 单轮通过不等于稳定通过

## 14.7 回归保护
- 相对当前稳定轮，任一任务 F1 下降 `> 0.03` 视为灾难回归
- 触发后回滚到 `last_good_config`
- 在自动迭代中，每轮只允许一个主因子变更，避免混杂因果
