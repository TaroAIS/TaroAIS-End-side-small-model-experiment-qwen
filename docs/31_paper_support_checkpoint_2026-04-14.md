# 31. Paper Support Checkpoint (2026-04-14)

## Ready Now

- mainline research framing is unified to `Qwen3 4B + canonical`
- monitor-side winner is documented:
  - `configs/agent_qwen3_4b_fast.yaml`
  - holdout overall F1 `0.3350`
  - holdout single_doc F1 `0.3347`
  - holdout multi_doc F1 `0.2885`
  - holdout code F1 `0.4282`
  - holdout p95 ratio `1.6362`
- failed and non-promoted rounds are documented:
  - Round 1 `multi_doc recall lift`
  - Round 2 `task-targeted`
  - Round 3 `code_multi_doc_compact`
  - Round 4 `code_only`
  - Round 5 `budgeted backbone`
- canonical execution infrastructure is now in-repo:
  - `scripts/cmd/run_sharded_canonical.ps1`
  - `scripts/concat_jsonl.py`
  - `docs/30_canonical_execution_log_2026-04-14.md`
  - `scripts/canonical_live_status.py`
  - `docs/33_canonical_live_status.md`

## Formal Evidence In Progress

- canonical baseline anchor:
  - output: `results/baseline_rag_formal_anchor_4b_canonical.jsonl`
  - log: `logs/canonical_baseline_full/stdout.log`
  - observed progress at `2026-04-14 19:34`: `1020 / 2550` rows (`40.0%`)
- after baseline merge:
  - run `agent_qwen3_4b_fast` canonical single-seed
  - evaluate canonical baseline vs canonical agent
- after canonical single-seed:
  - apply `docs/32_round6_trigger_plan.md`
  - watcher script: `scripts/cmd/run_round6_monitor_after_canonical.ps1`

## Still Needed For The Paper Package

1. canonical single-seed main table
2. canonical 3-seed confirmation
3. canonical budget-matched baseline
4. canonical single-round-strong baseline
5. grouped ablation tables:
   - quality
   - cost
   - stability
6. frozen student branch evidence:
   - holdout100
   - canonical final check

## Current Writing Guidance

- Use canonical as the only formal main conclusion.
- Use `dev100`, `holdout100`, and `quickgate30` only as monitor / promotion evidence.
- Do not claim a new Round 6 direction before canonical single-seed confirms where the real deficit is.
- If you need to report current progress before canonical is finished, describe it as:
  - `formal canonical baseline is running and has completed 6 / 15 shards (1020 / 2550 samples, 40.0%)`
  - `the best verified monitor-side configuration remains agent_qwen3_4b_fast`
