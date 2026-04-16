# 00 Manifest

本文件列出论文包中的全部核心文件、当前状态、来源和最终用途。

## 根目录文件

| 文件 | 状态 | 主要来源 | 用途 |
| --- | --- | --- | --- |
| `README.md` | ready | 当前包 | 新的唯一写作入口 |
| `00_manifest.md` | ready | 当前包 | 包内索引 |
| `01_storyline.md` | ready | 正式结果 + 现有实验口径 | 统一论文叙事 |
| `02_claim_to_evidence_matrix.md` | ready | `report/` + `docs/` | 防止 claim 漂移 |
| `03_source_of_truth.md` | ready | 正式 canonical 结果 + 运行日志 | 统一数字口径 |
| `04_writing_checklist.md` | ready | 当前包 | 写作和定稿检查 |
| `05_key_data_snapshot.md` | ready | 当前正式结果快照 | 快速查看关键数字 |

## `manuscript/`

| 文件 | 状态 | 主要来源 | 用途 |
| --- | --- | --- | --- |
| `conference_cn.md` | ready | 当前包 + 正式结果 | 会议稿主稿骨架 |
| `thesis_cn.md` | ready | 当前包 + 系统/实验文档 | 毕业论文复用骨架 |
| `section_prompts.md` | ready | 当前包 | 每章写法指南 |
| `title_abstract_variants.md` | ready | 当前包 + 正式结果 | 题目与摘要候选 |
| `limitations_and_threats.md` | ready | 正式结果 + 运行日志 | 局限性与威胁章节素材 |

## `evidence/`

| 文件 | 状态 | 主要来源 | 用途 |
| --- | --- | --- | --- |
| `results_master_table.md` | ready | `metrics_table.csv` | 主结果总表 |
| `task_breakdown.md` | ready | `task_metrics.csv` | 单任务结果解释 |
| `figures_manifest.md` | ready | `report/formal_paper_canonical_s42_current/` | 图表登记与配套结论 |
| `error_case_digest.md` | ready | `error_cases.jsonl` + 预测文件 | 成功/失败案例摘要 |
| `method_comparison_notes.md` | ready | 配置与实验口径 | 解释各方法在回答什么问题 |

## `appendix/`

| 文件 | 状态 | 主要来源 | 用途 |
| --- | --- | --- | --- |
| `appendix_cn.md` | ready | 当前包 + `docs/` | 附录主文件 |
| `codeqa_positioning.md` | ready | 正式结果 + 数据口径 | 解释 `code_qa` 的论文地位 |
| `citation_and_related_work_notes.md` | ready | `references.bib` + 当前研究定位 | 相关工作写作备忘 |

## `artifacts/`

| 文件 | 状态 | 主要来源 | 用途 |
| --- | --- | --- | --- |
| `artifacts/README.md` | ready | 当前包 | 说明随包快照结构 |
| `artifacts/canonical_single_seed/metrics_table.csv` | ready | 正式 report 复制 | 原始 overall 指标快照 |
| `artifacts/canonical_single_seed/task_metrics.csv` | ready | 正式 report 复制 | 原始分任务指标快照 |
| `artifacts/canonical_single_seed/key_task_summary.csv` | ready | 正式 report 复制 | 原始关键任务汇总快照 |
| `artifacts/canonical_single_seed/error_cases.jsonl` | ready | 正式 report 复制 | 原始错误案例快照 |

## `assets/`

| 文件 | 状态 | 主要来源 | 用途 |
| --- | --- | --- | --- |
| `assets/README.md` | ready | 当前包 | 说明图表原件结构 |
| `assets/figures/*.png` | ready | 正式 report 复制 | 图表原件，便于直接插图 |

## 旧材料如何使用

这些旧文件保留，但只作为 source material：

- `docs/25_论文实验章节初稿.md`
- `docs/29_论文支撑材料清单.md`
- `docs/37_论文结果总表模板.md`
- `docs/38_code_qa_外部效度补充.md`
- `docs/41_paper_canonical_execution_log_2026-04-16.md`

使用规则：

- 可以拆解、引用、迁移
- 不再直接当作主稿
- 不再作为论文数字的第一来源

## 本轮新增内容

本轮为了便于打包和分发，额外补充了：

- `05_key_data_snapshot.md`
- `artifacts/README.md`
- `assets/README.md`
- `artifacts/canonical_single_seed/*`
- `assets/figures/*`

这些新增内容不改变原有写作结构，只是让论文包更自带证据、更便于压缩分发。
