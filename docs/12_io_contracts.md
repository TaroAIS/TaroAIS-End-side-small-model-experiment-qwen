# 12. I/O 契约

## 12.1 `scripts/prepare_longbench_3tasks.py`
输入：
- 远程 `LongBench` 官方压缩包

输出：
- `data/main_eval/longbench_3tasks_test.jsonl`
- `data/manifests/longbench_3tasks_source.json`

约束：
- 每行必须通过 `schemas/dataset.schema.json`

## 12.2 `scripts/prepare_task_ext_corpus.py`
输入：
- `NarrativeQA`
- `Qasper`
- `HotpotQA`
- `MuSiQue`
- `RepoBench v1.1`

输出：
- `data/train_ext/single_doc/*`
- `data/train_ext/multi_doc/*`
- `data/train_ext/code_qa/*`
- `data/manifests/dataset_registry.json`
- `data/manifests/dataset_versions.json`

约束：
- 所有输出 JSONL 必须通过 `schemas/dataset.schema.json`

## 12.3 `scripts/build_combined_ext_sets.py`
输入：
- 各任务组 `merged_train.jsonl`
- 各任务组 `merged_valid.jsonl`

输出：
- `data/train_ext/combined_train.jsonl`
- `data/train_ext/combined_valid.jsonl`

## 12.4 `scripts/build_main_eval_sets_v2.py`
输入：
- `data/train_ext/combined_valid.jsonl`
- `data/main_eval/longbench_3tasks_test.jsonl`

输出：
- `data/main_eval/longbench_3tasks_dev100.jsonl`
- `data/main_eval/longbench_3tasks_holdout100.jsonl`
- `data/manifests/main_eval_split_manifest.json`

约束：
- `dev/holdout` 与 canonical 不得样本重叠

## 12.5 `scripts/build_corpus.py`
输入：
- `data/train_ext/combined_train.jsonl`

输出：
- `data/corpus_chunks.jsonl`
- `data/index/`

## 12.6 `run_baseline_rag.py`
输入：
- dataset JSONL
- `configs/baseline_rag.yaml`

输出：
- `results/baseline_*.jsonl`

约束：
- 每行通过 `schemas/result.schema.json`

## 12.7 `run_agent.py`
输入：
- dataset JSONL
- `configs/agent.yaml`
- `index_dir`

输出：
- `results/edge_agent*.jsonl`
- `results/run_x/metadata.json`
- 可选 `results/run_x/trace/{id}.json`

## 12.8 `evaluate.py`
输入：
- gold dataset JSONL
- 1..N 个 pred JSONL

输出：
- `report/metrics_table.csv`
- `report/task_metrics.csv`
- `report/key_task_summary.csv`
- `report/*.png`

约束：
- 指标口径见 `docs/14_metrics_definition.md`

## 12.9 `scripts/cmd/compare_controls.sh`
输入：
- `configs/baseline_budget_matched.yaml`
- `configs/baseline_single_round_strong.yaml`
- canonical dataset

输出：
- `results/baseline_budget_matched.jsonl`
- `results/baseline_single_round_strong.jsonl`

## 12.10 `scripts/cmd/main_formal.sh`
行为：
- 主实验默认入口
- 仅运行主实验与消融，不默认触发 student 分支

## 12.11 `scripts/cmd/student_branch.sh`
行为：
- 仅运行 student 数据蒸馏、训练与评测
- 设计上应在主配置冻结后单独执行

## 12.12 `scripts/cmd/calibrate_thresholds.sh`
输入：
- canonical dataset
- `baseline_rag`
- `baseline_budget_matched`
- `baseline_single_round_strong`
- 代表性 agent 配置

输出：
- `report_calibration/seed_*/metrics_table.csv`
- `report_calibration/calibration_method_summary.csv`
- `report_calibration/threshold_recommendation.json`
