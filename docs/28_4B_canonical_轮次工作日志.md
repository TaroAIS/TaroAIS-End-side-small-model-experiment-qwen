# 28. 4B canonical 轮次工作日志

## 2026-04-13 Round 0 校准记录

### 背景
- 主模型口径已经固定为 `Qwen3 4B`。
- 主结论数据集固定为 `LongBench_3tasks canonical`。
- 高频迭代工作台使用 `dev100 / holdout100 / quickgate30`。

### 已确认的起始事实
- 当前默认 `agent.yaml` 起点等价于 `agent_qwen3_4b_fast` 一类的保守 fast 配置。
- 该起点在小模型成本上更友好，但会明显压低 `multi_doc_qa` 的召回。
- 旧的 monitor gate 对 4B 来说偏严，特别是 `dev100` 上的 `single_doc_qa` 和 `p95 ratio`。

### 已有实测证据
- `formal_auto_r1_dev_20260413_033454`
  - baseline overall F1: `0.2877`
  - agent overall F1: `0.3332`
  - single_doc F1: `0.2013`
  - multi_doc F1: `0.2981`
  - code F1: `0.4333`
  - p95 ratio: `2.08`
- `fasttrack_holdout100_qwen3_4b`
  - baseline overall F1: `0.3027`
  - fast agent overall F1: `0.3350`
  - single_doc F1: `0.3347`
  - multi_doc F1: `0.2885`
  - code F1: `0.4282`
  - p95 ratio: about `1.49`
- `rerun_quickgate30_qwen3_fast_compare`
  - fast agent overall F1: `0.4017`
  - single_doc F1: `0.3683`
  - multi_doc F1: `0.2581`
  - code F1: `0.5787`

### 诊断
- 当前 fast 主线不是“完全无效”，而是“质量有增益，但 `multi_doc_qa` 被压得过狠”。
- `dev100` 上 `single_doc_qa` 只有 7 个样本，现阶段更适合做风险预警，不适合作为高门槛硬卡。
- `holdout100` 和 `quickgate30` 已经表明 4B fast 路线在 `single_doc_qa` 与 `code_qa` 上并不弱，真正拖住 overall 的是 `multi_doc_qa`。

### 本轮动作
- 将主配置从纯 fast 起点切到 `multi_doc recall lift`：
  - `retrieval.hybrid.max_candidates: 10 -> 11`
  - `multi_doc_qa.top_k_init: 2 -> 3`
  - `multi_doc_qa.top_k_iter: 1 -> 2`
  - `multi_doc_qa.max_new_tokens: 176 -> 192`
- 监测门槛按当前 4B 实测分布临时重标定：
  - `dev_target_overall_f1 = 0.33`
  - `dev_target_single_doc_f1 = 0.20`
  - `dev_target_p95_ratio = 2.15`
  - `holdout_target_overall_f1 = 0.33`
  - `holdout_target_single_doc_f1 = 0.30`
  - `holdout_target_p95_ratio = 1.75`
  - `quickgate_target_overall_f1 = 0.39`
  - `quickgate_target_single_doc_f1 = 0.32`
  - `quickgate_target_p95_ratio = 1.90`

### 当前状态
- Round 1 已按 `multi_doc recall lift` 配置启动。
- 本日志用于记录轮次判断和动作来源；正式 round snapshot 仍写入 `docs/24_实验快照_当前.md`。

## 2026-04-13 Round 1 中途观察（dev100 已完成）

### Round 1 dev100 结果
- baseline overall F1: `0.2877`
- agent overall F1: `0.3348`
- single_doc F1: `0.1766`
- multi_doc F1: `0.2982`
- code F1: `0.4438`
- p95 ratio: about `2.09`

### 相对 fast 起点的变化
- overall: `0.3332 -> 0.3348`，仅小幅上升。
- single_doc: `0.2013 -> 0.1766`，明显回撤。
- multi_doc: `0.2981 -> 0.2982`，基本不变。
- code: `0.4333 -> 0.4438`，有一定提升。
- 检索量：`avg_retrieved_chunks_total 3.47 -> 5.06`，但质量收益没有同步放大。

### 当前判断
- 这次“统一放宽 multi-doc 召回”的做法不够精准。
- 问题不只是 `top-k` 不够，而是 `4B` 在长上下文和多文档场景里对检索增量的利用效率有限。
- 单纯提高候选数和 multi-doc 检索深度，会把额外上下文成本扩散到其他任务，导致 `single_doc_qa` 回撤。

### 下一步候选动作
- 优先等待 `holdout100` 与 `quickgate30` 完整结果，确认这一趋势是不是只在 `dev100` 上出现。
- 若 `holdout100` 也不支持本轮改动，则下一轮应回到 fast 骨架，并尝试更定向的任务级策略：
  - 只增强 `multi_doc_qa` 的步骤预算，不放大全局候选池；
  - 或切到已有的 `code_multi_doc_compact` 一类强任务定向候选，而不是统一加检索。
- 已预备下一轮候选配置：`configs/agent_round2_task_targeted.yaml`

## 2026-04-13 Round 1 结论（dev100 + holdout100）

### holdout100 结果
- baseline overall F1: `0.3179`
- agent overall F1: `0.3261`
- single_doc F1: `0.3200`
- multi_doc F1: `0.2801`
- code F1: `0.4195`
- p95 ratio: about `1.64`

### 相对 fast 起点的变化
- overall: `0.3350 -> 0.3261`
- single_doc: `0.3347 -> 0.3200`
- multi_doc: `0.2885 -> 0.2801`
- code: `0.4282 -> 0.4195`

### Round 1 总结
- `multi_doc recall lift` 没有兑现预期收益。
- 在 `dev100` 上只带来极小的 overall 提升，同时拉低了 `single_doc_qa`。
- 在 `holdout100` 上则出现了三任务全线回撤，说明问题不是 monitor 偶然波动，而是策略方向本身不对。
- 因此 Round 1 应判定为失败轮次，不进入 `quickgate30` 与 `canonical` 晋级。

### 决策
- 回滚“放大全局候选池”的思路。
- Round 2 改用更强的任务级定向配置：
  - 基于 fast 骨架恢复全局候选池；
  - 只增强 `multi_doc_qa` 与 `code_qa`；
  - 避免把额外上下文成本扩散到 `single_doc_qa`。

## 2026-04-13 Round 2 中途观察（dev100 已完成）

### Round 2 dev100 结果
- baseline overall F1: `0.2877`
- agent overall F1: `0.3385`
- single_doc F1: `0.1597`
- multi_doc F1: `0.3159`
- code F1: `0.4242`
- p95 ratio: about `2.09`

### 相对 Round 1 的变化
- overall: `0.3348 -> 0.3385`
- single_doc: `0.1766 -> 0.1597`
- multi_doc: `0.2982 -> 0.3159`
- code: `0.4438 -> 0.4242`

### 当前判断
- 任务定向增强比 Round 1 更接近正确方向，因为它真正抬升了 `multi_doc_qa`，并带来 overall 改善。
- 但这组收益目前仍然是“用 `single_doc_qa` 和 `code_qa` 换来的”，说明任务间预算再分配还不够精细。
- 因为 overall 与 `multi_doc_qa` 已明显好于 Round 1，所以 Round 2 继续进入 `holdout100`，再判断这种权衡是否能被更大一点的监测集接受。

## 2026-04-13 Round 2 结论（dev100 + holdout100）

### holdout100 结果
- baseline overall F1: `0.3179`
- agent overall F1: `0.3234`
- single_doc F1: `0.2889`
- multi_doc F1: `0.2717`
- code F1: `0.4346`
- p95 ratio: about `1.65`

### 相对 Round 1 的变化
- overall: `0.3261 -> 0.3234`
- single_doc: `0.3200 -> 0.2889`
- multi_doc: `0.2801 -> 0.2717`
- code: `0.4195 -> 0.4346`

### Round 2 总结
- 任务定向增强确实把 `code_qa` 拉回来了，但同时牺牲了 `single_doc_qa` 与 `multi_doc_qa`。
- 在 `holdout100` 上，Round 2 仍然低于 Round 1，也低于历史 fast 起点。
- 这说明仅靠 fast 骨架上的轻量 task override 调整，已经难以把三任务同时拉高。

### 决策
- Round 2 同样判定为失败轮次，不进入 `quickgate30` 与 `canonical`。
- 下一轮不再做小步搜索，改为直接复核仓库里历史最强的 4B 候选：
  - `configs/agent_code_multi_doc_compact_candidate.yaml`
  - 如该候选在当前数据和后端条件下仍成立，再考虑把它收编为新的主线。

## 2026-04-13 Round 3 结论（历史强候选复核）

### dev100 结果
- overall F1: `0.3474`
- single_doc F1: `0.3179`
- multi_doc F1: `0.3264`
- code F1: `0.3959`
- p95 ratio: about `2.89`

### holdout100 结果
- overall F1: `0.3300`
- single_doc F1: `0.3011`
- multi_doc F1: `0.2837`
- code F1: `0.4293`
- p95 ratio: about `2.27`

### Round 3 总结
- 这是目前实际复核里 overall 最好的候选。
- 它成功把 `single_doc_qa` 和 `multi_doc_qa` 拉回到更像论文主线的水平。
- 但它仍然太重：`p95 ratio` 明显超标，而且 `holdout100` overall 仍未超过历史 fast 参照。

### 决策
- Round 3 不直接升格为主线，但可视为“质量 backbone”。
- 下一步有两个方向：
  - 验证 `configs/agent_code_only_candidate.yaml` 是否能给出更好的任务平衡；
  - 若没有更强候选，则在 Round 3 backbone 上做预算收缩，尝试降耗保质。

## 2026-04-13 Round 4 结论（code_only 候选）

### dev100 结果
- overall F1: `0.3238`
- single_doc F1: `0.3179`
- multi_doc F1: `0.2884`
- code F1: `0.3959`
- p95 ratio: about `2.89`

### 结论
- Round 4 相比 Round 3 只保住了 `single_doc_qa`，却明显丢掉了 `multi_doc_qa`。
- 因此 Round 4 在 `dev100` 就可判定为劣于 Round 3，不进入 `holdout100`。

## 2026-04-13 Round 5 结论（budgeted backbone）

### holdout100 结果
- overall F1: `0.3295`
- single_doc F1: `0.2756`
- multi_doc F1: `0.2837`
- code F1: `0.4333`
- p95 ratio: about `2.21`

### 结论
- Round 5 确实比 Round 3 稍微降了成本，但 overall 也轻微回落。
- `single_doc_qa` 的损失仍然偏大，`p95 ratio` 也没有降到可接受区间。
- 因此 Round 5 可视为“Round 3 backbone 的降耗尝试”，但还不足以替代最终主线。

## 当前最优主线结论

### 在当前后端与当前 baseline anchor 下的 apples-to-apples 结果
- `agent_qwen3_4b_fast.yaml`
  - holdout overall F1: `0.3350`
  - holdout single_doc F1: `0.3347`
  - holdout multi_doc F1: `0.2885`
  - holdout code F1: `0.4282`
  - holdout p95 ratio: `1.6362`
- `agent_code_multi_doc_compact_candidate.yaml`
  - holdout overall F1: `0.3300`
  - holdout p95 ratio: `2.2661`
- `agent_round5_backbone_budgeted.yaml`
  - holdout overall F1: `0.3295`
  - holdout p95 ratio: `2.2078`

### 最终选择
- 当前真实环境下，`agent_qwen3_4b_fast.yaml` 仍然是最好的默认主线。
- 它不是质量最高的所有局部配置，但它给出了最好的“质量-延迟-稳定性”平衡。
- 后续若继续冲 canonical，应该以 fast current 为默认入口，再考虑在其基础上做极小步改动。
