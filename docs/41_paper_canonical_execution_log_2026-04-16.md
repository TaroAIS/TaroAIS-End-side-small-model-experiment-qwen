# 41. Paper Canonical Execution Log (2026-04-16)

## Scope

- target: rerun the true paper-grade `Qwen3 4B + LongBench_3tasks canonical` single-seed formal pass
- paper config: `results/frozen_configs/agent_qwen3_4b_paper_canonical_s42.yaml`
- canonical gold: `data/main_eval/longbench_3tasks_test.jsonl`
- baseline anchor: `results/baseline_rag_formal_anchor_4b_canonical.jsonl`
- agent output: `results/edge_agent_formal_paper_canonical_s42.jsonl`
- final report dir: `report/formal_paper_canonical_s42_current`

## Why This Rerun Was Opened

- The previously running full canonical job was still tied to the old fast-track identity:
  - profile/objective came from `configs/agent_qwen3_4b_fast.yaml`
  - report/output paths were still `formal_fast_canonical_*`
- That older run was useful as an engineering rehearsal, but it was not the clean frozen paper run.
- For the thesis / paper story, canonical must be:
  - a new round
  - a frozen config
  - a dedicated output path
  - an independently observable and resumable execution chain

## Cleanup Before Relaunch

- stopped the old background fast-track canonical chain:
  - old guardian
  - old pipeline
  - old live watcher
  - old round-6 watcher
  - old active shard workers
- no old result files were deleted
- the new paper run uses a fresh output/report identity and its own guardian paths

## First Launch Incident And Fix

### Incident A: wrong live shard path

- symptom:
  - the new paper live page showed `1696` completed shard lines immediately
  - that number belonged to the older fast canonical shard directory
- root cause:
  - `scripts/cmd/run_paper_canonical_guardian.ps1` did not pass `--agent_shard_dir`
  - the live watcher therefore fell back to the old default shard directory
- fix:
  - added `--agent_shard_dir results/_sharded/edge_agent_formal_paper_canonical_s42`

### Incident B: detached PowerShell children exited immediately

- symptom:
  - guardian kept reporting `pipeline_missing`
  - pipeline and summary watcher PIDs were created, but their PowerShell processes died immediately
- root cause:
  - `scripts/supervise_canonical.py` launched Windows helper processes with `DETACHED_PROCESS`
  - that mode was stable for Python children but not for the PowerShell helper scripts used here
- fix:
  - changed the detached launch mode to `CREATE_NEW_PROCESS_GROUP` only
  - added `stdin=subprocess.DEVNULL` for child launches

## Relaunch Record

- relaunch time: `2026-04-16 03:56`
- launcher:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cmd/launch_paper_canonical_guardian.ps1
```

- main runtime chain:
  - guardian: `scripts/cmd/run_paper_canonical_guardian.ps1`
  - supervisor core: `scripts/supervise_canonical.py`
  - canonical pipeline: `scripts/cmd/run_canonical_single_seed_pipeline.ps1`
  - shard runner: `scripts/cmd/run_sharded_canonical.ps1`
  - live watcher: `scripts/canonical_live_status.py`
  - post summary watcher: `scripts/cmd/run_paper_canonical_summary_watch.ps1`

## Observability Entry Points

- live markdown: `docs/39_paper_canonical_live_status.md`
- rolling snapshots: `docs/40_paper_canonical_analysis_snapshots.md`
- reentry prompt: `docs/42_paper_canonical_reentry_prompt.md`
- supervisor json: `report_live/paper_canonical_supervisor_status.json`
- incident bundle: `report_live/paper_canonical_incident_bundle.json`
- guardian events: `logs/paper_canonical_guardian/events.jsonl`
- pipeline stdout: `logs/paper_canonical_single_seed_pipeline/stdout.log`
- shard runner state: `results/_sharded/edge_agent_formal_paper_canonical_s42/_runner_state.json`

## Initial Healthy Status

- confirmed healthy at: `2026-04-16 04:08`
- stage: `agent_running`
- baseline lines: `2550 / 2550`
- effective agent shard lines: `23 / 2550`
- running shards:
  - `[0:170)`
  - `[170:340)`
- anomalies: `0`
- warnings: `0`

## Early Runtime Interpretation

- the run is now in the correct paper identity and no longer mixed with the older fast-track canonical job
- the guardian can:
  - detect missing helper processes
  - restart them
  - keep shard progress without deleting completed work
- the live watcher and snapshot file are now pointed at the paper shard directory, so progress numbers are trustworthy
- the current early throughput is still slow, so wall-clock remains the main bottleneck rather than correctness

## Next Monitoring Rules

1. Keep the frozen config unchanged during this canonical pass.
2. Monitor shard growth and anomaly count through `docs/39` and `docs/40`.
3. If a shard stalls or crashes, let the guardian recover first; only patch code if the logs show a real repeatable fault.
4. After canonical metrics are written, record the main result delta and decide the next single-factor optimization step in a new round snapshot.

## Stall Investigation And Mitigation (2026-04-16 12:43)

- target shard: `edge_agent_formal_paper_canonical_s42_0340_0510`
- observed symptom:
  - the shard advanced normally to `18 / 170`
  - then stopped emitting stdout, stderr, and JSONL growth
  - the old runner only detected the issue at shard level after long idle time and marked it `retry_pending`
- root-cause judgement:
  - this does **not** look like a deterministic bad sample or broken dataset row
  - the suspected next sample in that shard (`global idx 358`, Qasper) was reproduced separately and completed successfully:
    - sample index build: about `24s`
    - full `run_sample`: about `85s`
  - therefore the more likely failure mode is:
    - a rare sample-level stall under concurrent execution
    - with the old code lacking a sample-level timeout guard
    - and the old runner re-queued stalled shards behind fresh pending shards

### Code Fixes Applied

- `run_agent.py`
  - added a persistent per-shard sample worker process
  - added a default sample-level hard timeout (`600s` by default)
  - if one sample hangs, terminate only that worker, write a structured fallback result with `error_count=1`, and continue
  - added `agent sample start` / `agent sample done` logging so shard activity is visible between progress checkpoints
  - preserved extra `runtime` config fields instead of overwriting the whole block
- `scripts/cmd/run_sharded_canonical.ps1`
  - changed pending scheduling so `retry_pending` shards are launched before fresh `pending` shards

### Runtime Effect After Patch

- the old pipeline/runner children were stopped while keeping all partial shard JSONL files
- guardian restarted the canonical pipeline at `2026-04-16 12:42`
- the resumed runner immediately prioritized the stalled shard:
  - launched `[340:510)` first
  - then launched `[510:680)`
- the new shard stdout confirmed the new protections were active:
  - `agent sample worker enabled: timeout_s=600`
  - per-sample start/done logs appeared
- the previously stalled shard resumed forward progress beyond the old `18`-row boundary

## Eval Recovery And Formal Result (2026-04-17 01:30)

- symptom:
  - agent generation finished at `2550 / 2550`
  - formal report was still missing
  - guardian kept restarting the pipeline because `evaluate.py` failed in formal mode
- root cause:
  - the baseline anchor file `results/baseline_rag_formal_anchor_4b_canonical.jsonl` still contained `2` rows with:
    - `backend_mode=unknown`
    - `error_count=1`
  - formal evaluation rejects any non-`real` backend row
  - the failing ids were:
    - `lb_2wikimqa_7940c60a5ff2d81b62d118253577d1d891057ca4`
    - `lb_2wikimqa_0c43156b7d6bc17425a89dc6c6d48fc8c2c72ac9`
- mitigation:
  - extracted those `2` dataset rows into a temporary JSONL
  - re-ran `run_baseline_rag.py` on just those rows
  - both repaired outputs returned with:
    - `backend_mode=real`
    - `error_count=0`
  - atomically replaced the two bad rows in:
    - `results/baseline_rag_formal_anchor_4b_canonical.jsonl`
    - `results/_sharded/baseline_rag_formal_anchor_4b_canonical/baseline_rag_formal_anchor_4b_canonical_0850_1020.jsonl`
    - `results/_sharded/baseline_rag_formal_anchor_4b_canonical/baseline_rag_formal_anchor_4b_canonical_1020_1190.jsonl`
- verification:
  - baseline backend counts after repair:
    - `real: 2550`
    - `unknown: 0`
  - manual formal evaluation then completed successfully and wrote:
    - `report/formal_paper_canonical_s42_current/metrics_table.csv`
    - `report/formal_paper_canonical_s42_current/task_metrics.csv`

### Formal Single-Seed Result

- overall F1:
  - baseline: `0.2552`
  - edge_agent_4b: `0.3351`
  - delta: `+0.0799`
- task F1:
  - `single_doc_qa`: `0.2513 -> 0.2150` (`-0.0363`)
  - `multi_doc_qa`: `0.2104 -> 0.2392` (`+0.0288`)
  - `code_qa`: `0.2941 -> 0.5020` (`+0.2079`)
- latency and stability:
  - p95 latency: `41436.8 ms -> 55228.4 ms`
  - p95 ratio: about `1.333`
  - OOM count: `0 -> 3`

### Interpretation

- this run is **not** a wasted run:
  - the expensive agent pass completed and was fully reusable
  - the only blocking issue was formal evaluation hygiene on `2` baseline rows
- the current paper-canonical signal is now clear:
  - overall canonical result is strongly positive
  - `code_qa` is a major win
  - `multi_doc_qa` is a moderate positive
  - `single_doc_qa` remains the main regression and should be the next optimization target
