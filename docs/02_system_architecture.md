# 02. 系统架构（工程分层 + 数据流）

## 分层结构（Codex 必须生成）
- llm/（driver_local / driver_hf）
- retrieval/（chunking / index_faiss）
- agent/（edge_reasoning_agent / memory / fact_extractor / prompts）
- training/（distill_controller / train_qlora）
- metrics/（qa_metrics）
- utils/（schema/metadata/nvml/timer/io）

## 数据流
Dataset(JSONL) -> Chunking -> VectorIndex -> (BaselineRAG | EdgeAgent) -> results JSONL -> evaluate -> report CSV/PNG

## 强制契约
- 数据/结果/metadata 必须通过 schemas 校验（schemas/*.json）
- 每次 run 必须写 results/run_x/metadata.json（可复现）
