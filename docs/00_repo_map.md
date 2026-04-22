# 仓库导引

这份导引只做一件事：帮助第一次进入仓库的人快速判断哪些目录是正式主线，哪些目录是历史遗留、论文产物或运行输出。

## 一、最先看的目录

- `README.md`
  - 仓库入口、完整实验命令、数据来源与主流程说明。
- `scripts/cmd/`
  - 所有推荐执行的命令入口。
- `configs/`
  - baseline、controls、agent、student 等配置。
- `data/main_eval/`
  - 正式主评测与监测数据。
- `data/train_ext/`
  - 扩展训练池。
- `report/`
  - 实验评测输出与论文图输出。

## 二、正式主线

当前正式主线是：

1. 准备数据：`prepare_remote_strict.sh`
2. 建索引：`index.sh`
3. 跑基线：`baseline.sh`
4. 跑强对照：`compare_controls.sh`
5. 跑 agent：`agent.sh`
6. 做评测：`eval.sh`
7. 做消融：`ablations.sh`
8. 做多种子确认：`bench_key_tasks.sh`

一键入口：

```bash
bash scripts/cmd/main_formal.sh
```

## 三、哪些目录不要当成主实验入口

- `data/minilongbench_*`
  - 历史兼容小数据，不是当前主实验默认集。
- `report_tiny*`
  - smoke 或安装检查输出。
- `report_live/`
  - 运行监控、事件日志、守护进程状态。
- `papers/`
  - 论文、答辩、图表、审校材料，是实验结果的下游写作层。
- `docs_dataset_upgrade/`
  - 数据升级过程文档。

## 四、结果文件怎么看

一次完整实验之后，优先看：

- `results/*.jsonl`
  - 模型推理输出。
- `report/metrics_table.csv`
  - 总体指标。
- `report/task_metrics.csv`
  - 任务分解指标。
- `report/key_task_summary.csv`
  - 关键任务聚合指标。
- `report/error_cases.jsonl`
  - 错误样例。
- `report/paper_figures/`
  - 论文图与答辩图。

## 五、论文相关

如果目标是写论文，而不是跑实验，优先看：

- `papers/final_delivery_submission_ready/`
- `papers/final_delivery_with_r/`
- `papers/final_delivery_submission_ready/source_data/`

如果目标是继续改实验，不要把 `papers/` 里的结果副本误当成唯一数据源，应优先确认 `report/`、`results/` 与 `data/` 的当前状态。
