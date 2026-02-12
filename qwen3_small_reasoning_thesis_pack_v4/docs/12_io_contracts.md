# 12. I/O 契约（每个脚本的输入输出必须固定）

> 目的：让 Codex 100% 按统一格式落盘，避免“字段对不上”。

## 12.1 scripts/prepare_minilongbench.py
输入：无（或从 HF/GitHub 下载；具体由实现决定）  
输出：`data/minilongbench_{split}.jsonl`  
约束：每行必须通过 schemas/dataset.schema.json

## 12.2 scripts/build_corpus.py
输入：`data/minilongbench_train.jsonl`  
输出：
- `data/corpus_chunks.jsonl`（chunks）
- `data/index/`（FAISS index + mapping）  
约束：chunk_id 必须唯一；doc_id+chunk_id 可追溯到原文 offset。

## 12.3 run_baseline_rag.py
输入：
- dataset JSONL
- configs/baseline_rag.yaml  
输出：`results/baseline_*.jsonl`  
约束：每行通过 schemas/result.schema.json

## 12.4 run_agent.py
输入：
- dataset JSONL
- configs/agent.yaml
- index_dir（默认 data/index）  
输出：
- `results/edge_agent*.jsonl`（预测）
- `results/run_x/metadata.json`（run 元信息）
- 可选：`results/run_x/trace/{id}.json`（单样本 trace）  
约束：schema 必过；metadata 通过 schemas/run_metadata.schema.json

## 12.5 evaluate.py
输入：
- gold dataset JSONL
- 1..N 个 pred JSONL  
输出：
- report/metrics_table.csv
- report/*.png
- report/error_cases.jsonl（可选）  
约束：指标口径见 docs/14、docs/15；图文件名见 docs/13。
