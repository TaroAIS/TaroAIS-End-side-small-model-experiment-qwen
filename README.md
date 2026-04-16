# Qwen3 4B Canonical 实验工程

更新日期：2026-04-16

本仓库当前唯一正式主线是：
- 主模型：`qwen3:4b`
- 主结论数据：`LongBench_3tasks canonical`
- 主问题：在严格预算下，`4B` 小模型能否通过任务路由式 agent 协议，在 `single_doc_qa / multi_doc_qa / code_qa` 三任务上实现平衡提升，同时守住时延与稳定性门槛

## 当前仓库状态
- 正式主流程：`prepare -> index -> baseline -> compare_controls -> agent -> eval -> ablations -> canonical 3-seed confirm`
- Student 分支：`distill -> train_student -> eval_student`
- 结果口径：
  - `canonical` 是唯一论文主结论
  - `dev100 / holdout100 / quickgate30` 只负责高频迭代、风险监测与晋级预筛
  - `student` 是主配置冻结后的附加效率实验，不参与主结论通过判定
  - `code_qa` 保留为高价值亮点任务，但不单独承担整篇论文主结论

## 论文故事
- 不讲“大模型绝对更强”，而讲“`4B` 小模型在长上下文下存在任务异质性，统一协议会牺牲平衡性”
- 主方法统一表述为：`budget-aware task-routed protocol for 4B long-context reasoning`
- 主贡献统一表述为：
  - 提出适配 `4B` 长文档场景的任务路由式 agent 协议
  - 在 `LongBench_3tasks canonical` 上相对强对照实现三任务平衡提升
  - 用分组消融解释质量、成本与稳定性来源

## 快速开始
1. 冒烟检查：
- `bash scripts/cmd/smoke.sh`

2. 正式主实验：
- `bash scripts/cmd/main_formal.sh`

3. 门槛校准：
- `bash scripts/cmd/calibrate_thresholds.sh`

4. 自动迭代：
- `python scripts/auto_iterate_formal.py`

5. 主配置冻结后 student 分支：
- `bash scripts/cmd/student_branch.sh`

6. `code_qa` 外部效度补充：
- `bash scripts/cmd/code_generalization_appendix.sh`

## 数据口径
- 主结论：`data/main_eval/longbench_3tasks_test.jsonl`
- 高频监测：`data/main_eval/longbench_3tasks_dev100.jsonl`
- 风险监测：`data/main_eval/longbench_3tasks_holdout100.jsonl`
- 晋级预筛：`data/main_eval/longbench_3tasks_quickgate30.jsonl`
- 扩展训练池：
  - `data/train_ext/combined_train.jsonl`
  - `data/train_ext/combined_valid.jsonl`
- 代码泛化补充：
  - `data/main_eval/code_generalization/code_generalization_appendix.jsonl`
  - 由 `RepoBench Python valid + RepoBench Java valid` 固定抽样构成

## 主结果如何解读
- 主文主表只看 `canonical + 4B + 3-seed + CI`
- `baseline_budget_matched` 回答“收益是否只是多花预算”
- `baseline_single_round_strong` 回答“收益是否只是单轮检索更强”
- `dev100 / holdout100 / quickgate30` 只回答“当前 candidate 是否值得晋级 canonical”
- `code_qa` 的大幅提升只作为亮点证据，不替代 canonical 主结论
- `student` 只回答“冻结后的主策略能否进一步压缩”

## 文档入口
- 实验手册：[docs/23_experiment_playbook.md](/d:/taroPROJECT/end%20design/TaroAIS-End-side-small-model-experiment-qwen/docs/23_experiment_playbook.md)
- 门槛说明：[docs/14_metrics_definition.md](/d:/taroPROJECT/end%20design/TaroAIS-End-side-small-model-experiment-qwen/docs/14_metrics_definition.md)
- 消融设计：[docs/06_experiment_design_and_ablation.md](/d:/taroPROJECT/end%20design/TaroAIS-End-side-small-model-experiment-qwen/docs/06_experiment_design_and_ablation.md)
- I/O 契约：[docs/12_io_contracts.md](/d:/taroPROJECT/end%20design/TaroAIS-End-side-small-model-experiment-qwen/docs/12_io_contracts.md)
- 论文实验章节草稿：[docs/25_论文实验章节初稿.md](/d:/taroPROJECT/end%20design/TaroAIS-End-side-small-model-experiment-qwen/docs/25_%E8%AE%BA%E6%96%87%E5%AE%9E%E9%AA%8C%E7%AB%A0%E8%8A%82%E5%88%9D%E7%A8%BF.md)
- 论文结果总表模板：[docs/37_论文结果总表模板.md](/d:/taroPROJECT/end%20design/TaroAIS-End-side-small-model-experiment-qwen/docs/37_%E8%AE%BA%E6%96%87%E7%BB%93%E6%9E%9C%E6%80%BB%E8%A1%A8%E6%A8%A1%E6%9D%BF.md)
- `code_qa` 外部效度补充：[docs/38_code_qa_外部效度补充.md](/d:/taroPROJECT/end%20design/TaroAIS-End-side-small-model-experiment-qwen/docs/38_code_qa_%E5%A4%96%E9%83%A8%E6%95%88%E5%BA%A6%E8%A1%A5%E5%85%85.md)
- 命令说明：[scripts/cmd/README.md](/d:/taroPROJECT/end%20design/TaroAIS-End-side-small-model-experiment-qwen/scripts/cmd/README.md)
