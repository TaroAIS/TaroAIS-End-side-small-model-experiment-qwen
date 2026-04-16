# 36. Runtime Guard And Resume

## Goal

This document defines the "best-effort no-reset" runtime policy for the canonical 4B experiment.

The preferred behavior is:

1. keep the canonical run alive
2. preserve completed shard outputs
3. resume from partial progress
4. restart only missing helper processes
5. leave a complete handoff bundle for a fresh Codex session

## Core Files

- shard runner state:
  - `results/_sharded/edge_agent_formal_fast_canonical_s42/_runner_state.json`
- live status:
  - `docs/33_canonical_live_status.md`
  - `report_live/canonical_live_status.json`
- supervisor outputs:
  - `report_live/canonical_supervisor_status.json`
  - `report_live/codex_incident_bundle.json`
  - `docs/35_codex_reentry_prompt.md`
- guardian event log:
  - `logs/canonical_guardian/events.jsonl`

## Runtime Components

- `run_agent.py`
  - supports shard ranges
  - supports `--resume`
  - flushes partial JSONL incrementally

- `run_baseline_rag.py`
  - supports shard ranges
  - supports `--resume`
  - flushes partial JSONL incrementally

- `scripts/cmd/run_sharded_canonical.ps1`
  - executes canonical shards with bounded concurrency
  - records shard progress and retry state
  - skips healthy completed shards on rerun

- `scripts/canonical_live_status.py`
  - rebuilds the live markdown/json from shard state
  - appends periodic analysis snapshots

- `scripts/supervise_canonical.py`
  - detects missing helper processes
  - refreshes live status
  - emits bundle + reentry prompt
  - logs guardian actions

## Recovery Policy

- Never delete finished shard JSONL just because the pipeline was interrupted.
- Prefer `resume + retry` over full restart.
- Treat the merged final JSONL as secondary during execution; the shard state JSON is authoritative mid-run.
- If the pipeline process disappears while shard workers are still running, do not start a second overlapping agent runner.
- If only helper processes are missing, restart helpers first:
  - live watcher
  - round6 watcher
  - pipeline wrapper

## Standard Commands

- one-shot supervisor refresh:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cmd/supervise_canonical.ps1 -Apply -RefreshLiveOnce
```

- foreground guardian loop:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cmd/run_canonical_guardian.ps1
```

- background guardian loop:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cmd/launch_canonical_guardian.ps1
```

- manual pipeline restart:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cmd/run_canonical_single_seed_pipeline.ps1
```

## Current Canonical Runtime Snapshot

- baseline final: `2550 / 2550`
- effective agent shard progress: `1067 / 2550`
- completed shards: `6 / 15`
- running shards: `2`
- pending shards: `7`
- anomalies at last guardian cycle: `0`
- warnings at last guardian cycle: `0`

## Expected Operator Behavior

- Read the reentry prompt first if the original Codex session is gone.
- Use the supervisor status JSON for the latest machine-readable state.
- Use the live markdown for a human-readable progress page.
- Use the guardian event log to reconstruct what actions were automatically applied.
