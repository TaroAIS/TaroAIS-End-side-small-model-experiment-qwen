# 验收测试清单（v4）

## A. 功能验收
- [ ] `make smoke`：baseline + agent + evaluate 全链路跑通
- [ ] `make all`：索引 + baseline + agent + evaluate 全链路跑通
- [ ] 输出文件存在：results/*.jsonl、report/*.csv、report/*.png
- [ ] OOM 次数为 0

## B. Schema 验收
- [ ] dataset JSONL 通过 schemas/dataset.schema.json
- [ ] results JSONL 通过 schemas/result.schema.json
- [ ] metadata.json 通过 schemas/run_metadata.schema.json
- [ ] facts（若输出）通过 schemas/fact.schema.json

## C. 复现与日志
- [ ] 每次 run 保存 config snapshot 与 metadata.json
- [ ] latency 分解、gpu mem peak/mean、steps、retrieval count 可追溯
- [ ] 至少 1 条样本导出可解释 trace（见 docs/16_trace_example.md）

## D. 方法消融
- [ ] think_off / iterative_off / memory_sliding / inj_defense_off 至少跑 3 个
