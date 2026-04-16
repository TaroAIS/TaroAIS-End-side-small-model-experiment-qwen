param(
    [string]$FrozenConfig = "results/frozen_configs/agent_qwen3_4b_paper_canonical_s42.yaml",
    [int]$StallSeconds = 1800,
    [int]$PollSeconds = 120,
    [int]$LivePollSeconds = 120
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$python = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
$script = Join-Path $repoRoot "scripts\\supervise_canonical.py"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python executable not found: $python"
}

$args = @(
    $script,
    "--dataset", "data/main_eval/longbench_3tasks_test.jsonl",
    "--baseline", "results/baseline_rag_formal_anchor_4b_canonical.jsonl",
    "--agent", "results/edge_agent_formal_paper_canonical_s42.jsonl",
    "--baseline_shard_dir", "results/_sharded/baseline_rag_formal_anchor_4b_canonical",
    "--baseline_state", "results/_sharded/baseline_rag_formal_anchor_4b_canonical/_runner_state.json",
    "--agent_shard_dir", "results/_sharded/edge_agent_formal_paper_canonical_s42",
    "--runner_state", "results/_sharded/edge_agent_formal_paper_canonical_s42/_runner_state.json",
    "--pipeline_pid", "logs/paper_canonical_single_seed_pipeline/pid.txt",
    "--live_pid", "logs/paper_canonical_live_status/pid.txt",
    "--round6_pid", "logs/paper_canonical_summary_watch/pid.txt",
    "--pipeline_log", "logs/paper_canonical_single_seed_pipeline/stdout.log",
    "--pipeline_stderr", "logs/paper_canonical_single_seed_pipeline/stderr.log",
    "--live_log", "logs/paper_canonical_live_status/stdout.log",
    "--live_stderr", "logs/paper_canonical_live_status/stderr.log",
    "--round6_log", "logs/paper_canonical_summary_watch/stdout.log",
    "--round6_stderr", "logs/paper_canonical_summary_watch/stderr.log",
    "--report_dir", "report/formal_paper_canonical_s42_current",
    "--live_status_json", "report_live/paper_canonical_live_status.json",
    "--live_status_md", "docs/39_paper_canonical_live_status.md",
    "--snapshot_history_md", "docs/40_paper_canonical_analysis_snapshots.md",
    "--live_snapshot_state_json", "report_live/paper_canonical_snapshot_state.json",
    "--guardian_events", "logs/paper_canonical_guardian/events.jsonl",
    "--status_out", "report_live/paper_canonical_supervisor_status.json",
    "--bundle_out", "report_live/paper_canonical_incident_bundle.json",
    "--prompt_out", "docs/42_paper_canonical_reentry_prompt.md",
    "--pipeline_script", "scripts/cmd/run_canonical_single_seed_pipeline.ps1",
    "--pipeline_dataset", "data/main_eval/longbench_3tasks_test.jsonl",
    "--pipeline_baseline_out", "results/baseline_rag_formal_anchor_4b_canonical.jsonl",
    "--pipeline_agent_config", $FrozenConfig,
    "--pipeline_agent_out", "results/edge_agent_formal_paper_canonical_s42.jsonl",
    "--pipeline_report_dir", "report/formal_paper_canonical_s42_current",
    "--pipeline_run_tag", "formal_paper_canonical_s42_current",
    "--pipeline_shard_size", "170",
    "--pipeline_concurrency", "2",
    "--pipeline_seed", "42",
    "--pipeline_poll_seconds", "60",
    "--pipeline_stall_seconds", "$StallSeconds",
    "--pipeline_max_retries_per_shard", "2",
    "--post_watch_enabled",
    "--post_watch_name", "paper canonical summary watcher",
    "--post_watch_script", "scripts/cmd/run_paper_canonical_summary_watch.ps1",
    "--post_watch_report_dir", "report/formal_paper_canonical_s42_current",
    "--post_watch_poll_seconds", "120",
    "--post_watch_seed", "42",
    "--stall_seconds", "$StallSeconds",
    "--poll_seconds", "$PollSeconds",
    "--live_poll_seconds", "$LivePollSeconds",
    "--apply",
    "--loop",
    "--stop_when_done",
    "--refresh_live_once"
)

& $python @args
if ($LASTEXITCODE -ne 0) {
    throw "supervise_canonical.py failed with exit code $LASTEXITCODE"
}
