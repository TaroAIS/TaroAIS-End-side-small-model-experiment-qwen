# 22. Experiment Update 2026-04-13

## 本轮重构结论
- 主模型从旧大模型主线切换为 `Qwen3 4B`
- 主结论固定为 `LongBench_3tasks canonical`
- `dev100 / holdout100 / quickgate30` 降为监测与晋级预筛
- `student` 从主流程拆出，改为冻结后附加实验

## 当前正式主流程
- `main_formal.sh`
  - `prepare -> index -> baseline -> compare_controls -> agent -> eval -> ablations -> canonical 3-seed confirm`

## 当前对照组
- `baseline_rag`
- `baseline_budget_matched`
- `baseline_single_round_strong`
- `edge_agent`

## 当前自动迭代口径
- 每轮先跑 `dev100 + holdout100 + quickgate30`
- 监测通过后才晋级 `canonical`
- 每轮只允许一个主因子变化
