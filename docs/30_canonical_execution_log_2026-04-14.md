# 30. Canonical Execution Log (2026-04-14)

## Scope

- objective: run the `Qwen3 4B + canonical` formal anchor on full `LongBench_3tasks`
- baseline target: `results/baseline_rag_formal_anchor_4b_canonical.jsonl`
- next target after baseline: `agent_qwen3_4b_fast` canonical single-seed

## Why this log exists

- The current repository has already been refactored to `4B + canonical`, but the formal full-canonical anchor had not been completed yet.
- A direct one-shot baseline run on `2550` canonical rows was too long and only produced partial traces.
- To make the canonical path reproducible and monitorable, the repo now includes a dedicated sharded runner:
  - `scripts/cmd/run_sharded_canonical.ps1`
  - `scripts/concat_jsonl.py`

## Probe Results

| mode | sample_count | elapsed_seconds | observation |
| --- | ---: | ---: | --- |
| serial baseline probe | 20 | 497.0 | stable but too slow for full canonical |
| 2-way parallel probe | 40 | 694.9 | best throughput / stability tradeoff |
| 3-way parallel probe | 60 | 1007.5 | only marginal gain vs 2-way |
| 4-way parallel probe | 40 | 746.7 | slower than 2-way |

## Runner Decision

- dataset: `data/main_eval/longbench_3tasks_test.jsonl`
- total_rows: `2550`
- shard_size: `170`
- shard_count: `15`
- concurrency: `2`
- reason: best observed wall-clock efficiency without adding instability

## Formal Launch Record

- launch_time: `2026-04-14 13:57:49`
- launcher_command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cmd/run_sharded_canonical.ps1 `
  -Mode baseline `
  -Config configs/baseline_rag.yaml `
  -Dataset data/main_eval/longbench_3tasks_test.jsonl `
  -Out results/baseline_rag_formal_anchor_4b_canonical.jsonl `
  -ShardSize 170 `
  -Concurrency 2
```

- stdout_log: `logs/canonical_baseline_full/stdout.log`
- stderr_log: `logs/canonical_baseline_full/stderr.log`
- pid_file: `logs/canonical_baseline_full/pid.txt`
- merged_output: `results/baseline_rag_formal_anchor_4b_canonical.jsonl`

## Automated Follow-up Pipeline

- watcher_script: `scripts/cmd/run_canonical_single_seed_pipeline.ps1`
- watcher_stdout: `logs/canonical_single_seed_pipeline/stdout.log`
- watcher_stderr: `logs/canonical_single_seed_pipeline/stderr.log`
- watcher_pid_file: `logs/canonical_single_seed_pipeline/pid.txt`
- watcher_start_time: `2026-04-14 14:06:03`

### Pipeline behavior

1. Wait until `results/baseline_rag_formal_anchor_4b_canonical.jsonl` reaches `2550` lines.
2. Launch canonical single-seed agent run for `configs/agent_qwen3_4b_fast.yaml`.
3. Run `evaluate.py` on the merged baseline and agent outputs.
4. Write the final report to `report/formal_fast_canonical_s42_current`.
5. Print overall and per-task summary lines into the pipeline log.

## Round 6 Monitor Watcher

- watcher_script: `scripts/cmd/run_round6_monitor_after_canonical.ps1`
- watcher_stdout: `logs/round6_monitor_after_canonical/stdout.log`
- watcher_stderr: `logs/round6_monitor_after_canonical/stderr.log`
- watcher_pid_file: `logs/round6_monitor_after_canonical/pid.txt`
- watcher_start_time: `2026-04-14 15:39:47`

### Watcher behavior

1. Wait for `report/formal_fast_canonical_s42_current/metrics_table.csv`.
2. Parse canonical overall, per-task F1, and p95 ratio.
3. Stop immediately if the fast line already passes the canonical gate.
4. Stop immediately if latency has already exceeded the main threshold.
5. Otherwise choose exactly one Round 6 monitor candidate:
   - `configs/agent_round6_multi_doc_only_lift.yaml`, or
   - `configs/agent_round6_code_only_lift.yaml`
6. Run the chosen candidate on:
   - `quickgate30`
   - `holdout100`

## Live Status Watcher

- watcher_script: `scripts/canonical_live_status.py`
- watcher_stdout: `logs/canonical_live_status/stdout.log`
- watcher_stderr: `logs/canonical_live_status/stderr.log`
- watcher_pid_file: `logs/canonical_live_status/pid.txt`
- watcher_start_time: `2026-04-14 19:41:45`
- output_markdown: `docs/33_canonical_live_status.md`
- output_json: `report_live/canonical_live_status.json`

### Watcher behavior

1. Re-read the canonical baseline log and shard directory every `300` seconds.
2. Recompute completed shards, completed samples, throughput, and rough ETA.
3. Mirror pipeline and Round 6 watcher tails into a live status page.
4. Stop automatically after canonical summary metrics become available.

## Current Status At Log Creation

- first two shards launched successfully:
  - `[0:170)`
  - `[170:340)`
- detached runner confirmed stable on smaller probes before the full launch
- current promoted monitor winner remains `configs/agent_qwen3_4b_fast.yaml`

## Runtime Notes Discovered During Monitoring

- `run_baseline_rag.py` writes the shard JSONL only at the end of each shard.
- `run_baseline_rag.py` also creates the `results/run_*` metadata directory only after the shard has finished.
- Because of that behavior, the correct mid-run status signal is process CPU growth, not output-file growth.
- During monitoring, an older one-shot canonical baseline process from `2026-04-14 00:32` was still alive and sharing the same target output path.
- That stale one-shot process was terminated so the new sharded baseline could remain the only formal canonical anchor run.

## Working Conclusions

- The current bottleneck is no longer script correctness; it is canonical wall-clock.
- The 4B fast line is still the best monitor-side default because it preserves the best quality / latency balance on `holdout100`.
- Canonical single-seed evidence should be generated before introducing Round 6 changes, otherwise the optimization loop will drift away from the formal paper target.

## Latest Observed Status (2026-04-14 19:34)

- completed_shards: `6 / 15`
- completed_samples: `1020 / 2550`
- canonical_progress: `40.0%`
- currently_running_ranges:
  - `[1020:1190)`
  - `[1190:1360)`
- observed_rate_from_completed_shards: `193.1 samples/hour`
- rough_eta_from_last_completion: `~7.9 hours`

### Completed shard outputs

- `results/_sharded/baseline_rag_formal_anchor_4b_canonical/baseline_rag_formal_anchor_4b_canonical_0000_0170.jsonl`
- `results/_sharded/baseline_rag_formal_anchor_4b_canonical/baseline_rag_formal_anchor_4b_canonical_0170_0340.jsonl`
- `results/_sharded/baseline_rag_formal_anchor_4b_canonical/baseline_rag_formal_anchor_4b_canonical_0340_0510.jsonl`
- `results/_sharded/baseline_rag_formal_anchor_4b_canonical/baseline_rag_formal_anchor_4b_canonical_0510_0680.jsonl`
- `results/_sharded/baseline_rag_formal_anchor_4b_canonical/baseline_rag_formal_anchor_4b_canonical_0680_0850.jsonl`
- `results/_sharded/baseline_rag_formal_anchor_4b_canonical/baseline_rag_formal_anchor_4b_canonical_0850_1020.jsonl`

## Next Actions

1. Wait for the full canonical baseline anchor to merge successfully.
2. Run `agent_qwen3_4b_fast` on canonical single-seed using the same sharded runner.
3. Evaluate baseline vs agent on canonical and compare against the current 4B thresholds.
4. If canonical is below target, open Round 6 with exactly one change factor:
   - `code_qa` budget lift, or
   - `multi_doc_qa` retrieval lift, or
   - keep fast frozen if canonical already satisfies the formal story.

## Runtime Recovery Event (2026-04-15 13:18)

- event: `canonical_agent_runner_recovered_with_resume_guard`
- root_cause_summary:
  - the original detached agent run on canonical had no incremental shard output and no stall guard
  - shard `[340:510)` and `[510:680)` remained active for a long period without visible forward progress
  - pipeline and live watcher startup also exposed Windows path-with-space launch issues
- code_changes_applied:
  - `run_agent.py`: incremental flush + resume support
  - `run_baseline_rag.py`: incremental flush + resume support
  - `scripts/cmd/run_sharded_canonical.ps1`: resume skip, shard state JSON, idle stall retry
  - `scripts/cmd/run_canonical_single_seed_pipeline.ps1`: restarted with the new runner path
  - `scripts/canonical_live_status.py`: runner-state aware live status and snapshot history
- recovery_result:
  - canonical agent was relaunched without discarding the first two completed shards
  - resumed runner state recorded `completed_shards=2`, `running_shards=2`, `pending_shards=11`
  - live status snapshot confirmed new shard files resumed incremental growth immediately after restart
- supporting_files:
  - `results/_sharded/edge_agent_formal_fast_canonical_s42/_runner_state.json`
  - `docs/33_canonical_live_status.md`
  - `docs/34_canonical_analysis_snapshots.md`

## Guardian Loop Upgrade (2026-04-15 23:02)

- event: `canonical_guardian_promoted_to_background_supervisor`
- motivation:
  - the experiment now needs long-running supervision, not just one-shot status dumps
  - if `pipeline`, `live watcher`, or `round6 watcher` exits unexpectedly, the repo should recover without losing shard progress
- new runtime scripts:
  - `scripts/supervise_canonical.py`
  - `scripts/cmd/supervise_canonical.ps1`
  - `scripts/cmd/run_canonical_guardian.ps1`
  - `scripts/cmd/launch_canonical_guardian.ps1`
- new runtime artifacts:
  - `report_live/canonical_supervisor_status.json`
  - `report_live/codex_incident_bundle.json`
  - `docs/35_codex_reentry_prompt.md`
  - `logs/canonical_guardian/events.jsonl`
  - `logs/canonical_guardian/stdout.log`
  - `logs/canonical_guardian/pid.txt`

### Guardian Behavior

1. Read shard runner state and compute effective agent progress from partial shard outputs.
2. Refresh `docs/33_canonical_live_status.md` and `report_live/canonical_live_status.json`.
3. Detect missing helper processes while canonical metrics are still unavailable.
4. Restart missing helper processes without deleting any finished shard JSONL.
5. Emit a handoff bundle and reentry prompt for a fresh Codex session.

### Observed Status At Guardian Launch

- stage: `agent_running`
- baseline_final_lines: `2550 / 2550`
- effective_agent_lines: `1067 / 2550`
- effective_agent_progress: `41.8%`
- active_shards:
  - `[1020:1190)` with `28` lines
  - `[1190:1360)` with `19` lines
- anomalies: `0`
- warnings: `0`

### Operational Conclusion

- canonical now has a background guardian in addition to the pipeline itself
- the preferred recovery action is `resume + restart helper`, never "clear shard outputs and restart the full run"
