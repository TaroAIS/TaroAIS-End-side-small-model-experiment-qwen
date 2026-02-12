# Codex Prompt（v4：包含全部增强项，按规范实现）

你是资深 LLM/ML 工程师。请在一个全新 Git 仓库中，严格根据本项目 docs/configs/schemas，生成一套可运行、可复现的实验代码，默认面向 RTX 4060 8GB。

## ✅ Definition of Done（必须全部满足）
### A. 数据与索引
1) `python scripts/prepare_minilongbench.py --out data/minilongbench_{split}.jsonl`
2) `python scripts/build_corpus.py --in data/minilongbench_train.jsonl --out data/corpus_chunks.jsonl --index_dir data/index/`
3) 所有输出 JSONL 必须通过 `schemas/dataset.schema.json` 或相应 schema 校验

### B. Baseline（Standard RAG）
4) `python run_baseline_rag.py --config configs/baseline_rag.yaml --dataset data/minilongbench_test.jsonl --out results/baseline_rag.jsonl`
5) baseline 输出通过 `schemas/result.schema.json`

### C. 你的方法（Edge-Reasoning Agent）
6) `python run_agent.py --config configs/agent.yaml --dataset data/minilongbench_test.jsonl --out results/edge_agent.jsonl`
要求：
- 严格执行 `<search>/<final>` 协议（见 docs/03_agent_algorithm.md）
- 实现 output protocol 状态机：PARSE -> (REPAIR once) -> FALLBACK
- 实现 memory 两种策略：sliding_window + fact_memory
- 实现 prompt injection defense（configs/agent.yaml 控制开关）
- 每个 run 保存 `results/run_x/metadata.json`（schema=schemas/run_metadata.schema.json）

### D. 自动评测与出图
7) `python evaluate.py --gold data/minilongbench_test.jsonl --pred results/baseline_rag.jsonl results/edge_agent.jsonl --out_dir report/`
输出：
- report/metrics_table.csv（列对齐 templates/metrics_table_template.csv）
- 至少三张图（文件名按 docs/13_figures_spec.md）

### E.（可选）Student-Controller 蒸馏与训练
8) `python scripts/distill_controller_data.py --teacher_config configs/teacher_distill.yaml --dataset data/minilongbench_train.jsonl --out data/student_train.jsonl`
要求：
- 蒸馏样本必须执行“质检规则”（见 docs/17_distill_data_quality.md）
9) `python train_student.py --config configs/train_qlora.yaml --train data/student_train.jsonl --out_dir checkpoints/student`

## 强约束
- Python >= 3.10
- 没 GPU 也不崩（CPU 兜底）
- 所有超参来自 YAML（configs/）
- 所有脚本提供 `--help`
- 所有 JSONL 读写做 schema 校验（jsonschema 库即可）
- 输出日志必须包含：latency breakdown、gpu mem peak/mean、检索次数、steps

## 必须生成的模块结构
- llm/driver_local.py
- llm/driver_hf.py
- retrieval/chunking.py
- retrieval/index_faiss.py
- agent/edge_reasoning_agent.py
- agent/memory.py
- agent/fact_extractor.py
- agent/prompts.py
- training/distill_controller.py
- training/train_qlora.py
- metrics/qa_metrics.py
- utils/nvml.py
- utils/timer.py
- utils/io.py
- utils/schema.py   # schema validate helper
- utils/metadata.py # run metadata writer

## 工程质量要求
- `bash scripts/run_smoke.sh` 必须能跑通（<=5 分钟）
- `make smoke`、`make all` 可用
- 任何 schema 不通过都要报错（不要默默吞）
