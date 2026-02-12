# 05. 数据集与数据管道（强约束）

## JSONL Schema
- 每条样本必须通过 schemas/dataset.schema.json

## Chunking
- chunk_size / overlap 固化在 configs
- chunk 输出包含 doc_id/chunk_id/offset/text
