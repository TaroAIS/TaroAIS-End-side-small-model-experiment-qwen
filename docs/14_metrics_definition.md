# 14. Metrics Definition

## 14.1 基础指标
- `EM`：标准归一化后的严格匹配。
- `F1`：字符/词级重叠 F1（与现有评测实现保持一致）。
- `P95 latency`：样本级 total latency 的 95 分位。
- `avg_steps`、`avg_retrieval`：推理行为成本指标。
- `oom_count`：运行失败代理指标，主实验要求为 0。

## 14.2 主实验硬门槛（canonical）
- 单 seed：
  - `overall F1 >= 0.37`
  - `single_doc_qa F1 >= 0.29`
  - `P95 ratio <= 1.8`
  - `oom_count = 0`
- 3-seed：
  - `mean overall F1 >= 0.37`
  - `mean single_doc_qa F1 >= 0.29`
  - `mean P95 ratio <= 1.8`
  - `all seeds oom_count = 0`

## 14.3 seed-level CI 与显著性
对每个 seed 计算三任务 `delta_F1 = F1(agent) - F1(baseline)`，再按 seed 统计：
- `mean_delta`
- `ci95 = 1.96 * std(delta)/sqrt(n)`（n=seed 数）
- `lower = mean_delta - ci95`
- `upper = mean_delta + ci95`

显著性判定：
- 至少 `2/3` 任务满足 `lower > 0`。

## 14.4 回归保护
- 相对当前最佳稳定轮，任一任务 F1 下降 `> 0.03` 视为灾难回归。
- 触发后自动回滚到 `last_good_config`，该轮仅记录不纳入候选最优。
