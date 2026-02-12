# 23. 实验手册（完整实验工程版）

本文档是实验解释的主入口，目标是回答三个问题：
- 实验到底执行了什么？
- 主对比实验怎么定义、怎么判定？
- 结果该如何解释，哪些能进论文主结论？

## 1) 研究问题与目标
目标不是单纯追求总均值，而是验证：
- 在关键任务 `multi_doc_qa + code_qa` 上，`edge_agent` 相对 `baseline_rag` 有稳定收益；
- 成本代价可接受（延迟和检索成本不失控）。

硬性门槛：
- `delta_f1_key >= 0.03`
- `latency_ratio <= 1.5`
- `retrieval_ratio <= 1.8`

其中：
- `delta_f1_key = agent_key_f1 - baseline_key_f1`
- `latency_ratio = agent_key_p95 / baseline_key_p95`
- `retrieval_ratio = agent_key_avg_retrieval / baseline_key_avg_retrieval`

## 2) 实验对象与分组
主对比分组：
- `baseline_rag`：单次 Top-K 检索 + 直接回答。
- `edge_agent`：协议状态机 + 迭代检索 + memory 策略 + 防注入。

消融分组：
- `think_off`
- `iterative_off`
- `memory_sliding`
- `inj_defense_off`

Student 路线：
- 数据蒸馏：`distill_controller_data.py`
- 训练：`train_student.py`
- 评测：`eval_student_controller.py`

## 3) 数据与检索范围
数据层分为两套：
- smoke：`smoke_data/minilongbench_tiny.jsonl`（3 条）
- formal：`data/minilongbench_{train|valid|test}.jsonl`（由脚本准备）

检索范围分为两种：
- `sample`：样本内检索（主实验默认，论文主表口径）
- `global`：全局索引检索（扩展实验，不混入主表）

## 4) 实验过程（输入/处理/输出）
### 4.1 主实验链路 A-D
1. `prepare`
- 输入：公开 MiniLongBench 数据或 smoke 数据
- 处理：字段转换、切分、schema 校验
- 输出：`data/minilongbench_{split}.jsonl`

2. `index`
- 输入：训练集 jsonl
- 处理：chunking + 建索引
- 输出：`data/index/`、`data/corpus_chunks.jsonl`

3. `baseline`
- 输入：评测集 + 索引（或 sample 内文档）
- 输出：`results/baseline*.jsonl`

4. `agent`
- 输入：评测集 + 索引 + agent config
- 输出：`results/edge_agent*.jsonl` + `results/run_*/metadata.json` (+ trace)

5. `evaluate`
- 输入：gold + pred
- 输出：`report/*.csv` + `report/*.png` + `report/error_cases.jsonl`

### 4.2 Student 链路 E
1. `distill`
- 输出：`data/student_train.jsonl` + `data/student_train_stats.json`

2. `train_student`
- 输出：`checkpoints/student/*`

3. `eval_student`
- 输出：`report_student/student_controller_eval.csv`
- 关键任务输出：`report_student/student_task_metrics.csv`、`report_student/student_key_task_summary.csv`

## 5) 结果解释模板（指标/误读/判定）
核心指标：
- 任务效果：`EM`、`F1`
- 成本：`p95_latency_ms`、`avg_retrieval`、token/chunk 成本列
- 稳定性：`gpu_peak_mb`、`oom_count`

常见误读：
- 只看总均值，不看关键任务子集。
- 只看 F1，不看 latency/retrieval 比例。
- 用 smoke 结果直接下 formal 结论。

通过判定：
- 必须看 `report_key/decision_gate.json` 的三项检查是否同时通过。

## 6) 主对比与关键任务结论
主结论实验由 `scripts/cmd/bench_key_tasks.sh` 产生，默认：
- `formal` 模式
- `retrieval_scope=sample`
- seeds：`42 123 2026`

关键文件：
- `report_key/seed_<n>/task_metrics.csv`
- `report_key/seed_<n>/key_task_summary.csv`
- `report_key/seed_aggregate.csv`（mean/std/95%CI）
- `report_key/decision_gate.json`（最终门槛判定）

## 7) 消融与 Student 的解释框架
消融解释：
- `think_off`：验证思考机制是否贡献效果。
- `iterative_off`：验证多轮检索策略是否必要。
- `memory_sliding`：比较 memory 策略对成本/效果权衡影响。
- `inj_defense_off`：验证注入防护对稳健性的贡献。

Student 解释：
- 行为指标：`trigger_acc`、`macro_f1`、`keyword_hit_rate`
- 端到端指标：`F1`、`avg_retrieval`、`avg_latency_ms`
- 看 teacher/student delta，避免只看单模型绝对值。

## 8) 可信性边界（smoke vs formal）
证据等级：
- `smoke`：只用于验证链路、格式、出图、schema；不进入论文主结论。
- `formal`：后端真实、依赖完整、严格失败语义；可进入主结论。

主结论最低条件：
- `run_mode=formal`
- `retrieval_scope=sample`
- 多 seed（默认 3）
- 输出完整且 schema 通过

## 9) 优化清单（P0/P1/P2）
P0（优先保证结论可信）：
- 增加 seed 数（例如 3 -> 5）降低 CI 不确定性。
- 固化 formal 环境快照（依赖版本、模型版本、驱动信息）。
- 对关键任务失败样本做系统化误差分桶。

P1（提升效果-成本平衡）：
- 针对 `multi_doc_qa` 优化 search 触发策略。
- 调整 memory/facts 注入策略，降低冗余 tokens。
- 对 `code_qa` 增加更稳定的检索关键词策略。

P2（增强论文可解释性）：
- 增加按任务类型的置信区间可视化图。
- 增加 Student 在关键任务子集的门槛判定文件。
- 增加不同 retrieval_scope 的扩展对照附录表。

## 当前快照（2026-02-12）
当前仓库内已有 smoke 快照产物：
- `report_tiny/`
- `report_key/`

`report_key/decision_gate.json` 当前状态：
- `pass=false`
- `delta_f1_key_mean=-0.0625`
- `latency_ratio_key_mean=3.6258`
- `retrieval_ratio_key_mean=3.5`

解释：这是 smoke 链路快照，用于验证流程和判定器，不用于论文主结论。最终结论以 formal 多 seed 结果为准。
