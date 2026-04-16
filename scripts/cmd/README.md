# scripts/cmd

所有默认脚本已经统一到 `Qwen3 4B + canonical 主结论` 主线。

## 通用约定
- 默认 `python3`
- 默认 `RUN_MODE=formal`
- 默认 `RETRIEVAL_SCOPE=sample`
- `smoke` 仅使用 `smoke_data/minilongbench_tiny.jsonl`

## 默认数据
- canonical：`data/main_eval/longbench_3tasks_test.jsonl`
- dev100：`data/main_eval/longbench_3tasks_dev100.jsonl`
- holdout100：`data/main_eval/longbench_3tasks_holdout100.jsonl`
- quickgate30：`data/main_eval/longbench_3tasks_quickgate30.jsonl`
- train：`data/train_ext/combined_train.jsonl`
- valid：`data/train_ext/combined_valid.jsonl`
- code appendix：`data/main_eval/code_generalization/code_generalization_appendix.jsonl`

## 脚本清单
- `bash scripts/cmd/smoke.sh`
  - 只做链路冒烟

- `bash scripts/cmd/main_formal.sh`
  - 正式论文主流程
  - 顺序：
    - `preflight -> prepare_remote_strict -> index -> baseline -> compare_controls -> agent -> eval -> ablations -> bench_key_tasks`

- `bash scripts/cmd/student_branch.sh`
  - 冻结后附加分支
  - 顺序：
    - `distill -> train_student -> eval_student`

- `bash scripts/cmd/code_generalization_appendix.sh`
  - `code_qa` 外部效度补充
  - 顺序：
    - 构造 `RepoBench Python valid + Java valid` 固定小样本
    - 运行 `baseline_rag_4b`
    - 运行 `edge_agent_4b`
    - 生成 Python / Java / combined 三份附录报告

- `bash scripts/cmd/baseline.sh`
  - 运行 `baseline_rag_4b`

- `bash scripts/cmd/compare_controls.sh`
  - 运行：
    - `baseline_budget_matched_4b`
    - `baseline_single_round_strong_4b`

- `bash scripts/cmd/agent.sh`
  - 运行 `edge_agent_4b`

- `bash scripts/cmd/eval.sh`
  - 生成主报告

- `bash scripts/cmd/ablations.sh`
  - 运行三组消融：
    - 质量：`iterative_off / memory_sliding / refine_gate_relaxed`
    - 成本：`budget_tight / topk_tight / max_steps_2`
    - 稳定性：`forced_retrieve_off / early_stop_off / promotion_guard_off`

- `bash scripts/cmd/bench_key_tasks.sh`
  - 在 canonical 上执行 3-seed 确认
  - 默认三任务一起汇总，不再只看 `multi_doc_qa + code_qa`

- `bash scripts/cmd/calibrate_thresholds.sh`
  - 在 canonical 上校准 4B 主门槛

## 推荐执行顺序
1. `bash scripts/cmd/smoke.sh`
2. `bash scripts/cmd/main_formal.sh`
3. `python scripts/auto_iterate_formal.py`
4. 主配置冻结后：`bash scripts/cmd/code_generalization_appendix.sh`
5. 主配置冻结后：`bash scripts/cmd/student_branch.sh`
