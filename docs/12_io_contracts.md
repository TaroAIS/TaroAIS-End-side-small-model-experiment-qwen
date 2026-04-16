# 12. I/O Contracts

## 12.1 主评测数据准备
- `scripts/prepare_longbench_3tasks.py`
  - 输出：
    - `data/main_eval/longbench_3tasks_test.jsonl`
    - `data/manifests/longbench_3tasks_source.json`
- `scripts/build_main_eval_sets_v2.py`
  - 输入：
    - `data/train_ext/combined_valid.jsonl`
    - `data/main_eval/longbench_3tasks_test.jsonl`
  - 输出：
    - `data/main_eval/longbench_3tasks_dev100.jsonl`
    - `data/main_eval/longbench_3tasks_holdout100.jsonl`
    - manifest JSON
- `data/main_eval/longbench_3tasks_quickgate30.jsonl`
  - 作为 canonical 晋级预筛集使用

## 12.2 扩展训练池
- `scripts/prepare_task_ext_corpus.py`
  - 输出：
    - `data/train_ext/single_doc/*.jsonl`
    - `data/train_ext/multi_doc/*.jsonl`
    - `data/train_ext/code_qa/*.jsonl`
- `scripts/build_combined_ext_sets.py`
  - 输出：
    - `data/train_ext/combined_train.jsonl`
    - `data/train_ext/combined_valid.jsonl`

## 12.3 补充代码泛化集
- `scripts/build_code_generalization_subset.py`
  - 输入：
    - `data/train_ext/code_qa/repobench_python_valid.jsonl`
    - `data/train_ext/code_qa/repobench_java_valid.jsonl`
  - 输出：
    - `data/main_eval/code_generalization/repobench_python_appendix.jsonl`
    - `data/main_eval/code_generalization/repobench_java_appendix.jsonl`
    - `data/main_eval/code_generalization/code_generalization_appendix.jsonl`
    - `data/manifests/code_generalization_appendix_manifest.json`
  - 说明：
    - 只用于 `code_qa` 外部效度补充
    - 不替代 canonical 主结论

## 12.4 推理与评测
- `run_baseline_rag.py`
  - 输入：dataset + baseline config
  - 输出：`results/baseline_*.jsonl`
- `run_agent.py`
  - 输入：dataset + agent config
  - 输出：`results/edge_agent*.jsonl`
- `evaluate.py`
  - 输入：gold dataset + 1..N prediction files
  - 输出：
    - `metrics_table.csv`
    - `task_metrics.csv`
    - figure artifacts
  - 契约：
    - 输出字段保持稳定
    - 不因 `4B + canonical` 主线切换而新增评测字段

## 12.5 命令入口
- `scripts/cmd/main_formal.sh`
  - 负责主实验与 canonical 3-seed confirm
- `scripts/cmd/student_branch.sh`
  - 负责 student 蒸馏、训练与评测
- `scripts/cmd/code_generalization_appendix.sh`
  - 负责 `code_qa` 外部效度补充
- `scripts/cmd/bench_key_tasks.sh`
  - 默认执行 canonical 3-seed 确认

## 12.6 轮次快照契约
- 自动迭代快照文档：`docs/24_实验快照_当前.md`
- 每轮必须记录：
  - round 编号
  - `config_profile / config_objective / config_snapshot`
  - config diff
  - 四路对照结果引用
  - `dev100 / holdout100 / quickgate30 / canonical` 指标
  - failure mode
  - next action
  - 若已触发，则补 canonical `3-seed confirm`

## 12.7 Student
- `scripts/cmd/distill.sh`
  - teacher 固定来自冻结后的 `4B edge_agent`
- `train_student.py`
  - CLI 形状不变：`--config --train --out_dir`
- `scripts/cmd/eval_student.sh`
  - 执行顺序固定：
    - `holdout100`
    - `canonical`
