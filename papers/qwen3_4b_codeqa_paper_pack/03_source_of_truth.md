# 03 Source Of Truth

## 一级来源：正文数字必须从这里拿

### 正式主结果

- 包内快照：
  - `artifacts/canonical_single_seed/metrics_table.csv`
  - `artifacts/canonical_single_seed/task_metrics.csv`
  - `artifacts/canonical_single_seed/key_task_summary.csv`
- 对应上游：
  - `report/formal_paper_canonical_s42_current/metrics_table.csv`
  - `report/formal_paper_canonical_s42_current/task_metrics.csv`
  - `report/formal_paper_canonical_s42_current/key_task_summary.csv`

这些文件负责：

- `overall F1`
- 各任务 F1
- `p50 / p95 latency`
- `avg_steps / avg_retrieval`
- `OOM`

### 本论文包的冻结转写页

- `evidence/results_master_table.md`
- `evidence/task_breakdown.md`
- `05_key_data_snapshot.md`

正文优先引用这些冻结页，而不是直接去翻 CSV。

## 二级来源：解释性材料可以从这里拿

- 包内快照：
  - `artifacts/canonical_single_seed/error_cases.jsonl`
- 上游生成位置：
  - `report/formal_paper_canonical_s42_current/error_cases.jsonl`
- `docs/41_paper_canonical_execution_log_2026-04-16.md`
- `docs/38_code_qa_外部效度补充.md`
- `docs/23_experiment_playbook.md`

这些材料用于：

- 解释实验流程
- 解释运行故障与恢复
- 解释 `code_qa` 的论文定位
- 解释案例、边界和附录材料

## 三级来源：只作历史材料，不作主稿事实依据

- `docs/25_论文实验章节初稿.md`
- `docs/24_实验快照_当前.md`
- `tmp/partial_eval_20260416/report_smoke/*`
- monitor 相关的 `dev100 / holdout100 / quickgate30` 文档

这些材料可以：

- 帮你找旧表述
- 帮你回忆历史轮次
- 帮你写“演化过程”或“附录日志”

这些材料不可以：

- 直接作为正式主结论数字来源
- 覆盖当前正式 canonical 结果
- 被写成“最终结论已经证实”

## 引用规则

### 正文可以直接写的数字

- `overall F1 = 0.3351`
- `baseline overall F1 = 0.2552`
- `code_qa = 0.2941 -> 0.5020`
- `multi_doc_qa = 0.2104 -> 0.2392`
- `single_doc_qa = 0.2513 -> 0.2150`
- `p95 ratio = 1.333`
- `OOM = 0 -> 3`

### 正文必须带限定语的数字

- 单 seed 正式结果
- `code_qa` 标题级亮点
- `single_doc` 回撤对应的失败模式

### 正文不要写的数字

- 未完成的 `3-seed`
- monitor 数字作为主结论
- partial eval 数字
- 旧 draft 中与当前结果冲突的历史数字

## 推荐统一措辞

### 正式结果

> 本文当前正式结论基于 `LongBench_3tasks canonical` 的单 seed 正式评测结果。

### 证据边界

> 除特别说明外，正文数字均来自当前包内冻结的 canonical 正式结果页及其随包 CSV 快照。

### 限定语

> 需要指出的是，当前结论仍为单 seed 正式结论，尚未完成 `3-seed confirm`。
