# scripts/cmd

每个脚本对应一个固定流程命令，默认已经切换到新的长文档数据体系。

## 通用约定
- 默认使用 `python3`
- 默认 `RUN_MODE=formal`
- 默认 `RETRIEVAL_SCOPE=sample`
- `smoke` 仍然只使用 `smoke_data/minilongbench_tiny.jsonl`

## 默认数据口径
- 主评测 canonical：`data/main_eval/longbench_3tasks_test.jsonl`
- 扩展监测 dev：`data/main_eval/longbench_3tasks_dev100.jsonl`
- 扩展监测 holdout：`data/main_eval/longbench_3tasks_holdout100.jsonl`
- 扩展训练池 train：`data/train_ext/combined_train.jsonl`
- 扩展训练池 valid：`data/train_ext/combined_valid.jsonl`

## 脚本清单
- `bash scripts/cmd/preflight_formal.sh`
  - 检查 LongBench 与扩展数据源可达、真实后端可用、绘图依赖可用。

- `bash scripts/cmd/smoke.sh`
  - 运行 smoke 全链路，仅用于链路验证。

- `bash scripts/cmd/main_formal.sh`
  - 论文主实验主链：
    - `preflight -> prepare_remote_strict -> index -> baseline -> compare_controls -> agent -> eval -> ablations`

- `bash scripts/cmd/student_branch.sh`
  - Student 独立分支：
    - `distill -> train_student -> eval_student`

- `bash scripts/cmd/prepare_remote.sh`
  - 生成新的主数据体系：
    - `LongBench_3tasks` 主评测集
    - 扩展训练池
    - `dev100/holdout100`

- `bash scripts/cmd/prepare_remote_strict.sh`
  - 与 `prepare_remote.sh` 相同，但用于 formal 严格链路。

- `bash scripts/cmd/prepare_offline.sh`
  - 仅供离线或历史兼容场景使用，不作为正式主流程默认入口。

- `bash scripts/cmd/index.sh`
  - 基于 `data/train_ext/combined_train.jsonl` 构建 chunk 与检索索引。

- `bash scripts/cmd/baseline.sh`
  - 在 `LongBench_3tasks` 上运行 baseline RAG。

- `bash scripts/cmd/compare_controls.sh`
  - 运行两个补充对照：
    - `baseline_budget_matched`
    - `baseline_single_round_strong`

- `bash scripts/cmd/agent.sh`
  - 在 `LongBench_3tasks` 上运行 edge agent。

- `bash scripts/cmd/eval.sh`
  - 基于 `LongBench_3tasks` 生成主报告。
  - 若补充对照结果存在，会自动并入主报告。

- `bash scripts/cmd/ablations.sh`
  - 在 `LongBench_3tasks` 上运行分组消融并输出 `report/ablations/`。
  - 分组：
    - 质量：`iterative_off / memory_sliding / refine_gate_relaxed`
    - 成本：`budget_tight`
    - 稳定性：`forced_retrieve_off / early_stop_off`

- `bash scripts/cmd/distill.sh`
  - 基于 `data/train_ext/combined_train.jsonl` 蒸馏 student 控制器训练数据。

- `bash scripts/cmd/train_student.sh`
  - 训练 student。

- `bash scripts/cmd/eval_student.sh`
  - 在 `LongBench_3tasks` 上评测 student 控制器与端到端行为。

- `bash scripts/cmd/bench_key_tasks.sh`
  - 在 `LongBench_3tasks` 上执行多 seed 关键任务补充 benchmark 并输出 `95%CI` 与门槛判定。
  - 默认输出目录：`report_key_supp/`

- `bash scripts/cmd/calibrate_thresholds.sh`
  - 运行门槛标定实验。
  - 统一比较：
    - `baseline_rag`
    - `baseline_budget_matched`
    - `baseline_single_round_strong`
    - `edge_agent`
    - 代表性 agent 变体
  - 输出：
    - `report_calibration/calibration_method_summary.csv`
    - `report_calibration/threshold_recommendation.json`

- `bash scripts/cmd/all.sh`
  - 兼容入口，等价于 `bash scripts/cmd/main_formal.sh`

## 推荐执行顺序
1. `bash scripts/cmd/smoke.sh`
2. `bash scripts/cmd/preflight_formal.sh`
3. `bash scripts/cmd/main_formal.sh`
4. 如需 student：`bash scripts/cmd/student_branch.sh`
5. 如需关键任务补充统计：`bash scripts/cmd/bench_key_tasks.sh`
6. 如需门槛重标定：`bash scripts/cmd/calibrate_thresholds.sh`
