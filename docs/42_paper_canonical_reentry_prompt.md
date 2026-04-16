# 35. Codex Reentry Prompt

Use this prompt in a new Codex session if the current session is unavailable.

## Context

- generated_at: `2026-04-17T01:31:40`
- summary: Guardian did not find a hard failure. Canonical stage is 'canonical_report_ready' with agent progress 100.0%.
- handoff_goal: Continue the canonical 4B experiment, fix anomalies if needed, and preserve resume state.

## What To Read First

- `D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\results\_sharded\edge_agent_formal_paper_canonical_s42\_runner_state.json`
- `D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\docs\39_paper_canonical_live_status.md`
- `D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\docs\40_paper_canonical_analysis_snapshots.md`
- `D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\logs\paper_canonical_single_seed_pipeline\stdout.log`

## Suggested Prompt

```text
Continue the canonical 4B experiment in this repository.
Start by reading the runner state JSON, live status markdown, supervisor bundle, and latest pipeline log.
Do not discard completed shard outputs. Prefer resume and retry over restarting from zero.
If anomalies are present, fix the smallest blocking issue, then continue the pipeline.
After recovery, update the experiment snapshots and summarize current progress.
```

## Suggested Commands

- restart_pipeline: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\scripts\cmd\run_canonical_single_seed_pipeline.ps1" -Dataset data/main_eval/longbench_3tasks_test.jsonl -BaselineOut results/baseline_rag_formal_anchor_4b_canonical.jsonl -AgentConfig results/frozen_configs/agent_qwen3_4b_paper_canonical_s42.yaml -AgentOut results/edge_agent_formal_paper_canonical_s42.jsonl -ReportDir report/formal_paper_canonical_s42_current -RunTag formal_paper_canonical_s42_current -ShardSize 170 -Concurrency 2 -Seed 42 -PollSeconds 60 -StallSeconds 1800 -MaxRetriesPerShard 2`
- restart_live_watcher: `"D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\.venv\Scripts\python.exe" "D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\scripts\canonical_live_status.py" --dataset data/main_eval/longbench_3tasks_test.jsonl --final_baseline results/baseline_rag_formal_anchor_4b_canonical.jsonl --final_agent results/edge_agent_formal_paper_canonical_s42.jsonl --baseline_shard_dir results/_sharded/baseline_rag_formal_anchor_4b_canonical --agent_shard_dir results/_sharded/edge_agent_formal_paper_canonical_s42 --baseline_state results/_sharded/baseline_rag_formal_anchor_4b_canonical/_runner_state.json --agent_state results/_sharded/edge_agent_formal_paper_canonical_s42/_runner_state.json --pipeline_log logs/paper_canonical_single_seed_pipeline/stdout.log --round6_log logs/paper_canonical_summary_watch/stdout.log --canonical_report_dir report/formal_paper_canonical_s42_current --out_json report_live/paper_canonical_live_status.json --out_md docs/39_paper_canonical_live_status.md --snapshot_md docs/40_paper_canonical_analysis_snapshots.md --snapshot_state_json report_live/paper_canonical_snapshot_state.json --poll_seconds 120 --stop_when_done`
- restart_round6_watcher: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\scripts\cmd\run_paper_canonical_summary_watch.ps1" -CanonicalReportDir report/formal_paper_canonical_s42_current -PollSeconds 120 -Seed 42`
- inspect_runner_state: `Get-Content -Path 'D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\results\_sharded\edge_agent_formal_paper_canonical_s42\_runner_state.json'`
- inspect_live_status: `Get-Content -Path 'D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\docs\39_paper_canonical_live_status.md'`

## Current Warnings

- none

## Current Anomalies

- none

## Latest Guardian Actions

- refreshed live status markdown/json once
