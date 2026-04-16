# 35. Codex Reentry Prompt

Use this prompt in a new Codex session if the current session is unavailable.

## Context

- generated_at: `2026-04-16T02:47:53`
- summary: Guardian did not find a hard failure. Canonical stage is 'agent_running' with agent progress 66.4%.
- handoff_goal: Continue the canonical 4B experiment, fix anomalies if needed, and preserve resume state.

## What To Read First

- `D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\results\_sharded\edge_agent_formal_fast_canonical_s42\_runner_state.json`
- `D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\docs\33_canonical_live_status.md`
- `D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\docs\34_canonical_analysis_snapshots.md`
- `D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\logs\canonical_single_seed_pipeline\stdout.log`

## Suggested Prompt

```text
Continue the canonical 4B experiment in this repository.
Start by reading the runner state JSON, live status markdown, supervisor bundle, and latest pipeline log.
Do not discard completed shard outputs. Prefer resume and retry over restarting from zero.
If anomalies are present, fix the smallest blocking issue, then continue the pipeline.
After recovery, update the experiment snapshots and summarize current progress.
```

## Suggested Commands

- restart_pipeline: `powershell -NoProfile -ExecutionPolicy Bypass -Command "& 'D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\scripts\cmd\run_canonical_single_seed_pipeline.ps1'"`
- restart_live_watcher: `D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\.venv\Scripts\python.exe D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\scripts\canonical_live_status.py --poll_seconds 120 --stop_when_done`
- restart_round6_watcher: `powershell -NoProfile -ExecutionPolicy Bypass -Command "& 'D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\scripts\cmd\run_round6_monitor_after_canonical.ps1'"`
- inspect_runner_state: `Get-Content -Path 'D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\results\_sharded\edge_agent_formal_fast_canonical_s42\_runner_state.json'`
- inspect_live_status: `Get-Content -Path 'D:\taroPROJECT\end design\TaroAIS-End-side-small-model-experiment-qwen\docs\33_canonical_live_status.md'`

## Current Warnings

- none

## Current Anomalies

- none

## Latest Guardian Actions

- refreshed live status markdown/json once
