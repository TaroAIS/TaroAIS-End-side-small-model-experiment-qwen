# 33. Canonical Live Status

- updated_at: `2026-04-16T02:49:03`
- stage: `agent_running`
- dataset: `data\main_eval\longbench_3tasks_test.jsonl`
- total_rows: `2550`
- baseline_final_lines: `2550 / 2550`
- agent_final_lines: `0 / 2550`
- agent_completed_shard_lines: `1696 / 2550`
- anomaly_count: `0`

## Agent Runner

- agent runner state: `unavailable`

## Anomalies

- none

## Pipeline Log Tail

```text
[2026-04-15T13:15:51] canonical single-seed pipeline start rows=2550
[2026-04-15T13:15:51] baseline anchor ready: D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\results\baseline_rag_formal_anchor_4b_canonical.jsonl
[2026-04-15T13:15:55] resume skip shard [0:170) lines=170
[2026-04-15T13:15:55] resume skip shard [170:340) lines=170
[2026-04-15T13:15:55] start edge_agent_formal_fast_canonical_s42 sharded run: mode=agent shards=15 concurrency=2 range=[0:2550) resume=True
[2026-04-15T13:15:55] launched shard 3/15: [340:510) pid=24976 attempt=1
[2026-04-15T13:15:55] launched shard 4/15: [510:680) pid=9960 attempt=1
[2026-04-15T15:59:54] completed shard [510:680) lines=170
[2026-04-15T15:59:58] launched shard 5/15: [680:850) pid=25400 attempt=1
[2026-04-15T16:10:58] completed shard [340:510) lines=170
[2026-04-15T16:11:01] launched shard 6/15: [850:1020) pid=21856 attempt=1
[2026-04-15T18:17:32] completed shard [850:1020) lines=170
[2026-04-15T18:17:33] launched shard 7/15: [1020:1190) pid=4764 attempt=1
[2026-04-15T22:46:32] completed shard [680:850) lines=170
[2026-04-15T22:46:32] launched shard 8/15: [1190:1360) pid=26756 attempt=1
[2026-04-16T00:54:34] completed shard [1020:1190) lines=170
[2026-04-16T00:54:35] launched shard 9/15: [1360:1530) pid=33172 attempt=1
[2026-04-16T01:00:52] completed shard [1190:1360) lines=170
[2026-04-16T01:00:52] launched shard 10/15: [1530:1700) pid=35364 attempt=1
```

## Round 6 Watcher Tail

```text
[2026-04-16T02:10:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:12:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:14:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:16:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:18:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:20:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:22:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:24:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:26:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:28:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:30:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:32:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:34:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:36:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:38:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:40:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:42:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:44:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:46:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
[2026-04-16T02:48:28] waiting for D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\report\formal_fast_canonical_s42_current\metrics_table.csv
```
