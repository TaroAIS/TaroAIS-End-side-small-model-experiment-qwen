#!/usr/bin/env python3
import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


DETACHED_FLAGS = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def read_tail(path: Path, lines: int = 20) -> List[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]


def read_pid(path: Path) -> Optional[int]:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None
    try:
        return int(text)
    except Exception:
        return None


def write_json(path: Path, payload: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, payload: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def process_exists(pid: Optional[int]) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        proc = subprocess.run(
            ["tasklist", "/FI", "PID eq {}".format(pid)],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        return False
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return str(pid) in output


def parse_iso(ts: str) -> Optional[datetime]:
    text = str(ts or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def preview_command(cmd: List[str]) -> str:
    parts = []
    for item in cmd:
        text = str(item)
        if not text:
            parts.append('""')
        elif any(ch.isspace() for ch in text) or '"' in text or "'" in text:
            parts.append('"{}"'.format(text.replace('"', '\\"')))
        else:
            parts.append(text)
    return " ".join(parts)


def canonical_stage(total_rows: int, baseline_lines: int, agent_lines: int, metrics_ready: bool) -> str:
    if metrics_ready:
        return "canonical_report_ready"
    if total_rows > 0 and agent_lines >= total_rows:
        return "agent_complete_pending_eval"
    if agent_lines > 0:
        return "agent_running"
    if total_rows > 0 and baseline_lines >= total_rows:
        return "baseline_complete_waiting_agent"
    if baseline_lines > 0:
        return "baseline_running"
    return "waiting"


def build_command_specs(repo_root: Path, args) -> Dict[str, Dict[str, object]]:
    python = repo_root / ".venv" / "Scripts" / "python.exe"
    live_script = repo_root / "scripts" / "canonical_live_status.py"
    pipeline_script = repo_root / args.pipeline_script

    pipeline_cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(pipeline_script),
        "-Dataset",
        args.pipeline_dataset,
        "-BaselineOut",
        args.pipeline_baseline_out,
        "-AgentConfig",
        args.pipeline_agent_config,
        "-AgentOut",
        args.pipeline_agent_out,
        "-ReportDir",
        args.pipeline_report_dir,
        "-RunTag",
        args.pipeline_run_tag,
        "-ShardSize",
        str(int(args.pipeline_shard_size)),
        "-Concurrency",
        str(int(args.pipeline_concurrency)),
        "-Seed",
        str(int(args.pipeline_seed)),
        "-PollSeconds",
        str(int(args.pipeline_poll_seconds)),
        "-StallSeconds",
        str(int(args.pipeline_stall_seconds)),
        "-MaxRetriesPerShard",
        str(int(args.pipeline_max_retries_per_shard)),
    ]

    live_cmd = [
        str(python),
        str(live_script),
        "--dataset",
        args.dataset,
        "--final_baseline",
        args.baseline,
        "--final_agent",
        args.agent,
        "--baseline_shard_dir",
        args.baseline_shard_dir,
        "--agent_shard_dir",
        args.agent_shard_dir,
        "--baseline_state",
        args.baseline_state,
        "--agent_state",
        args.runner_state,
        "--pipeline_log",
        args.pipeline_log,
        "--round6_log",
        args.round6_log,
        "--canonical_report_dir",
        args.report_dir,
        "--out_json",
        args.live_status_json,
        "--out_md",
        args.live_status_md,
        "--snapshot_md",
        args.snapshot_history_md,
        "--snapshot_state_json",
        args.live_snapshot_state_json,
        "--poll_seconds",
        str(int(args.live_poll_seconds)),
        "--stop_when_done",
    ]

    specs = {
        "pipeline": {
            "command": pipeline_cmd,
            "preview": preview_command(pipeline_cmd),
            "stdout": repo_root / args.pipeline_log,
            "stderr": repo_root / args.pipeline_stderr,
            "pid": repo_root / args.pipeline_pid,
        },
        "live": {
            "command": live_cmd,
            "preview": preview_command(live_cmd),
            "stdout": repo_root / args.live_log,
            "stderr": repo_root / args.live_stderr,
            "pid": repo_root / args.live_pid,
        },
    }

    if args.post_watch_enabled:
        post_script = repo_root / args.post_watch_script
        post_cmd = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(post_script),
            "-CanonicalReportDir",
            args.post_watch_report_dir,
            "-PollSeconds",
            str(int(args.post_watch_poll_seconds)),
            "-Seed",
            str(int(args.post_watch_seed)),
        ]
        specs["post"] = {
            "command": post_cmd,
            "preview": preview_command(post_cmd),
            "stdout": repo_root / args.round6_log,
            "stderr": repo_root / args.round6_stderr,
            "pid": repo_root / args.round6_pid,
        }
    return specs


def launch_detached(command: List[str], cwd: Path, stdout_path: Path, stderr_path: Path, pid_path: Path) -> int:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.parent.mkdir(parents=True, exist_ok=True)

    out_f = open(stdout_path, "ab")
    err_f = open(stderr_path, "ab")
    kwargs = {
        "cwd": str(cwd),
        "stdout": out_f,
        "stderr": err_f,
        "stdin": subprocess.DEVNULL,
    }
    if DETACHED_FLAGS:
        kwargs["creationflags"] = DETACHED_FLAGS
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(command, **kwargs)
    finally:
        out_f.close()
        err_f.close()
    pid_path.write_text(str(proc.pid), encoding="utf-8")
    return int(proc.pid)


def refresh_live_status_once(repo_root: Path, args) -> bool:
    python = repo_root / ".venv" / "Scripts" / "python.exe"
    script = repo_root / "scripts" / "canonical_live_status.py"
    try:
        proc = subprocess.run(
            [
                str(python),
                str(script),
                "--dataset",
                args.dataset,
                "--final_baseline",
                args.baseline,
                "--final_agent",
                args.agent,
                "--baseline_shard_dir",
                args.baseline_shard_dir,
                "--agent_shard_dir",
                args.agent_shard_dir,
                "--baseline_state",
                args.baseline_state,
                "--agent_state",
                args.runner_state,
                "--pipeline_log",
                args.pipeline_log,
                "--round6_log",
                args.round6_log,
                "--canonical_report_dir",
                args.report_dir,
                "--out_json",
                args.live_status_json,
                "--out_md",
                args.live_status_md,
                "--snapshot_md",
                args.snapshot_history_md,
                "--snapshot_state_json",
                args.live_snapshot_state_json,
                "--once",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        return proc.returncode == 0
    except Exception:
        return False


def build_status(
    repo_root: Path,
    dataset: Path,
    baseline: Path,
    agent: Path,
    runner_state_path: Path,
    pipeline_pid_path: Path,
    live_pid_path: Path,
    round6_pid_path: Path,
    pipeline_log: Path,
    live_log: Path,
    round6_log: Path,
    report_dir: Path,
    stall_seconds: int,
    command_specs: Dict[str, Dict[str, object]],
    live_status_md: Path,
    snapshot_history_md: Path,
    guardian_events_path: Path,
    post_watch_enabled: bool,
    post_watch_name: str,
) -> Dict:
    total_rows = count_lines(dataset)
    baseline_lines = count_lines(baseline)
    agent_lines = count_lines(agent)
    runner_state = load_json(runner_state_path) or {}
    shard_agent_lines = 0
    running_job_pids = []
    if runner_state:
        shard_agent_lines = int(sum(int(job.get("out_lines", 0) or 0) for job in runner_state.get("jobs", [])))
        running_job_pids = [
            int(job.get("pid", 0) or 0)
            for job in runner_state.get("jobs", [])
            if str(job.get("status", "")) == "running" and int(job.get("pid", 0) or 0) > 0
        ]
    effective_agent_lines = max(agent_lines, shard_agent_lines)

    pipeline_pid = read_pid(pipeline_pid_path)
    live_pid = read_pid(live_pid_path)
    round6_pid = read_pid(round6_pid_path)
    pipeline_running = process_exists(pipeline_pid)
    live_running = process_exists(live_pid)
    round6_running = process_exists(round6_pid) if post_watch_enabled else False
    metrics_ready = (report_dir / "metrics_table.csv").exists()

    anomalies = []
    warnings = []

    if runner_state:
        if int(runner_state.get("failed_shards", 0)) > 0:
            anomalies.append(
                {
                    "type": "failed_shards",
                    "message": "runner reports failed_shards={}".format(
                        runner_state.get("failed_shards", 0)
                    ),
                }
            )
        for job in runner_state.get("jobs", []):
            status = str(job.get("status", ""))
            if status != "running":
                continue
            last_activity = parse_iso(job.get("last_activity", ""))
            idle_seconds = None
            if last_activity is not None:
                idle_seconds = int((datetime.now() - last_activity).total_seconds())
                if idle_seconds >= stall_seconds:
                    anomalies.append(
                        {
                            "type": "running_shard_stalled",
                            "job": job.get("name", "unknown"),
                            "idle_seconds": idle_seconds,
                            "message": "running shard idle for {} seconds".format(idle_seconds),
                        }
                    )
            pid = int(job.get("pid", 0) or 0)
            if pid > 0 and not process_exists(pid):
                anomalies.append(
                    {
                        "type": "running_shard_pid_missing",
                        "job": job.get("name", "unknown"),
                        "pid": pid,
                        "message": "runner marks shard running but pid {} is missing".format(pid),
                    }
                )
            if idle_seconds is not None and idle_seconds >= max(600, stall_seconds // 3):
                warnings.append(
                    {
                        "type": "running_shard_slow",
                        "job": job.get("name", "unknown"),
                        "idle_seconds": idle_seconds,
                        "message": "running shard has been quiet for {} seconds".format(idle_seconds),
                    }
                )

    if not metrics_ready and not pipeline_running:
        anomalies.append(
            {
                "type": "pipeline_missing",
                "message": "pipeline process is not running while canonical report is still missing",
            }
        )
    if not metrics_ready and not live_running:
        warnings.append(
            {
                "type": "live_watcher_missing",
                "message": "live watcher is not running",
            }
        )
    if post_watch_enabled and not metrics_ready and not round6_running:
        warnings.append(
            {
                "type": "post_watcher_missing",
                "message": "{} is not running".format(post_watch_name),
            }
        )
    if effective_agent_lines >= total_rows > 0 and not metrics_ready:
        warnings.append(
            {
                "type": "eval_pending",
                "message": "agent output is complete but canonical metrics_table.csv is still missing",
            }
        )

    stage = canonical_stage(total_rows, baseline_lines, effective_agent_lines, metrics_ready)
    payload = {
        "updated_at": now_iso(),
        "stage": stage,
        "paths": {
            "repo_root": str(repo_root),
            "dataset": str(dataset),
            "baseline": str(baseline),
            "agent": str(agent),
            "runner_state": str(runner_state_path),
            "pipeline_log": str(pipeline_log),
            "live_log": str(live_log),
            "round6_log": str(round6_log),
            "report_dir": str(report_dir),
            "live_status_md": str(live_status_md),
            "snapshot_history_md": str(snapshot_history_md),
            "guardian_events": str(guardian_events_path),
        },
        "progress": {
            "total_rows": total_rows,
            "baseline_lines": baseline_lines,
            "agent_lines": agent_lines,
            "shard_agent_lines": shard_agent_lines,
            "effective_agent_lines": effective_agent_lines,
            "agent_progress": (effective_agent_lines / total_rows) if total_rows else 0.0,
            "metrics_ready": metrics_ready,
        },
        "processes": {
            "pipeline_pid": pipeline_pid,
            "pipeline_running": pipeline_running,
            "live_pid": live_pid,
            "live_running": live_running,
            "round6_pid": round6_pid,
            "round6_running": round6_running,
            "post_watch_name": post_watch_name if post_watch_enabled else "",
            "running_job_pids": running_job_pids,
        },
        "runner_state": runner_state,
        "anomalies": anomalies,
        "warnings": warnings,
        "tails": {
            "pipeline_log": read_tail(pipeline_log),
            "live_log": read_tail(live_log),
            "round6_log": read_tail(round6_log),
        },
        "suggested_commands": {
            "restart_pipeline": str(command_specs["pipeline"]["preview"]),
            "restart_live_watcher": str(command_specs["live"]["preview"]),
            "inspect_runner_state": "Get-Content -Path '{}'".format(str(runner_state_path)),
            "inspect_live_status": "Get-Content -Path '{}'".format(str(live_status_md)),
        },
    }
    if post_watch_enabled and "post" in command_specs:
        payload["suggested_commands"]["restart_round6_watcher"] = str(command_specs["post"]["preview"])
    return payload


def apply_remediation(status: Dict, command_specs: Dict[str, Dict[str, object]], repo_root: Path, refresh_live_once: bool, args) -> List[Dict]:
    actions = []
    metrics_ready = bool(status["progress"]["metrics_ready"])
    running_job_pids = [pid for pid in status["processes"].get("running_job_pids", []) if process_exists(pid)]

    if not metrics_ready and not status["processes"]["pipeline_running"] and not running_job_pids:
        spec = command_specs["pipeline"]
        pid = launch_detached(
            command=spec["command"],
            cwd=repo_root,
            stdout_path=spec["stdout"],
            stderr_path=spec["stderr"],
            pid_path=spec["pid"],
        )
        actions.append(
            {
                "type": "restart_pipeline",
                "pid": pid,
                "message": "restarted canonical pipeline",
            }
        )

    if not metrics_ready and not status["processes"]["live_running"]:
        spec = command_specs["live"]
        pid = launch_detached(
            command=spec["command"],
            cwd=repo_root,
            stdout_path=spec["stdout"],
            stderr_path=spec["stderr"],
            pid_path=spec["pid"],
        )
        actions.append(
            {
                "type": "restart_live_watcher",
                "pid": pid,
                "message": "restarted live watcher",
            }
        )

    if "post" in command_specs and not metrics_ready and not status["processes"]["round6_running"]:
        spec = command_specs["post"]
        pid = launch_detached(
            command=spec["command"],
            cwd=repo_root,
            stdout_path=spec["stdout"],
            stderr_path=spec["stderr"],
            pid_path=spec["pid"],
        )
        actions.append(
            {
                "type": "restart_round6_watcher",
                "pid": pid,
                "message": "restarted {}".format(args.post_watch_name),
            }
        )

    if refresh_live_once:
        ok = refresh_live_status_once(repo_root, args)
        actions.append(
            {
                "type": "refresh_live_once",
                "ok": bool(ok),
                "message": "refreshed live status markdown/json once" if ok else "live status refresh failed",
            }
        )

    return actions


def build_bundle(status: Dict) -> Dict:
    runner_state = status.get("runner_state") or {}
    running_jobs = [
        job
        for job in runner_state.get("jobs", [])
        if str(job.get("status", "")) == "running"
    ]
    pending_jobs = [
        job
        for job in runner_state.get("jobs", [])
        if str(job.get("status", "")) == "pending"
    ]

    headline = []
    if status["anomalies"]:
        headline.append("Guardian found {} anomaly/anomalies.".format(len(status["anomalies"])))
    else:
        headline.append("Guardian did not find a hard failure.")
    headline.append(
        "Canonical stage is '{}' with agent progress {:.1f}%.".format(
            status["stage"], status["progress"]["agent_progress"] * 100.0
        )
    )

    return {
        "generated_at": status["updated_at"],
        "summary": " ".join(headline),
        "handoff_goal": "Continue the canonical 4B experiment, fix anomalies if needed, and preserve resume state.",
        "status": {
            "stage": status["stage"],
            "total_rows": status["progress"]["total_rows"],
            "baseline_lines": status["progress"]["baseline_lines"],
            "agent_lines": status["progress"]["agent_lines"],
            "shard_agent_lines": status["progress"]["shard_agent_lines"],
            "effective_agent_lines": status["progress"]["effective_agent_lines"],
            "metrics_ready": status["progress"]["metrics_ready"],
        },
        "processes": status["processes"],
        "anomalies": status["anomalies"],
        "warnings": status["warnings"],
        "actions_applied": status.get("guardian", {}).get("actions_applied", []),
        "running_jobs": running_jobs,
        "pending_jobs_preview": pending_jobs[:4],
        "paths": status["paths"],
        "tails": status["tails"],
        "suggested_commands": status["suggested_commands"],
        "next_operator_steps": [
            "Inspect anomalies first. If there are none, continue monitoring until canonical report is ready.",
            "If pipeline is missing and there are no active shard workers, restart it with the provided restart command.",
            "Prefer resume and retry over deleting any completed shard output.",
            "After canonical report appears, continue with evaluation interpretation and frozen paper-canonical follow-up.",
        ],
    }


def write_reentry_prompt(path: Path, bundle: Dict):
    lines = [
        "# 35. Codex Reentry Prompt",
        "",
        "Use this prompt in a new Codex session if the current session is unavailable.",
        "",
        "## Context",
        "",
        "- generated_at: `{}`".format(bundle["generated_at"]),
        "- summary: {}".format(bundle["summary"]),
        "- handoff_goal: {}".format(bundle["handoff_goal"]),
        "",
        "## What To Read First",
        "",
        "- `{}`".format(bundle["paths"]["runner_state"]),
        "- `{}`".format(bundle["paths"]["live_status_md"]),
        "- `{}`".format(bundle["paths"]["snapshot_history_md"]),
        "- `{}`".format(bundle["paths"]["pipeline_log"]),
        "",
        "## Suggested Prompt",
        "",
        "```text",
        "Continue the canonical 4B experiment in this repository.",
        "Start by reading the runner state JSON, live status markdown, supervisor bundle, and latest pipeline log.",
        "Do not discard completed shard outputs. Prefer resume and retry over restarting from zero.",
        "If anomalies are present, fix the smallest blocking issue, then continue the pipeline.",
        "After recovery, update the experiment snapshots and summarize current progress.",
        "```",
        "",
        "## Suggested Commands",
        "",
        "- restart_pipeline: `{}`".format(bundle["suggested_commands"]["restart_pipeline"]),
        "- restart_live_watcher: `{}`".format(bundle["suggested_commands"]["restart_live_watcher"]),
        "- restart_round6_watcher: `{}`".format(bundle["suggested_commands"]["restart_round6_watcher"]),
        "- inspect_runner_state: `{}`".format(bundle["suggested_commands"]["inspect_runner_state"]),
        "- inspect_live_status: `{}`".format(bundle["suggested_commands"]["inspect_live_status"]),
        "",
        "## Current Warnings",
        "",
    ]
    if bundle["warnings"]:
        for item in bundle["warnings"]:
            lines.append("- {}".format(item.get("message", "warning")))
    else:
        lines.append("- none")
    lines.extend(["", "## Current Anomalies", ""])
    if bundle["anomalies"]:
        for item in bundle["anomalies"]:
            lines.append("- {}".format(item.get("message", "anomaly")))
    else:
        lines.append("- none")
    lines.extend(["", "## Latest Guardian Actions", ""])
    if bundle.get("actions_applied"):
        for item in bundle["actions_applied"]:
            lines.append("- {}".format(item.get("message", "action")))
    else:
        lines.append("- none")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def log_guardian_event(repo_root: Path, status: Dict):
    event = {
        "ts": status["updated_at"],
        "stage": status["stage"],
        "agent_progress": status["progress"]["agent_progress"],
        "anomaly_count": len(status["anomalies"]),
        "warning_count": len(status["warnings"]),
        "actions_applied": status.get("guardian", {}).get("actions_applied", []),
    }
    append_jsonl(Path(status["paths"]["guardian_events"]), event)


def run_cycle(args, command_specs: Dict[str, Dict[str, object]]) -> Dict:
    repo_root = Path(__file__).resolve().parents[1]
    status = build_status(
        repo_root=repo_root,
        dataset=repo_root / args.dataset,
        baseline=repo_root / args.baseline,
        agent=repo_root / args.agent,
        runner_state_path=repo_root / args.runner_state,
        pipeline_pid_path=repo_root / args.pipeline_pid,
        live_pid_path=repo_root / args.live_pid,
        round6_pid_path=repo_root / args.round6_pid,
        pipeline_log=repo_root / args.pipeline_log,
        live_log=repo_root / args.live_log,
        round6_log=repo_root / args.round6_log,
        report_dir=repo_root / args.report_dir,
        stall_seconds=int(args.stall_seconds),
        command_specs=command_specs,
        live_status_md=repo_root / args.live_status_md,
        snapshot_history_md=repo_root / args.snapshot_history_md,
        guardian_events_path=repo_root / args.guardian_events,
        post_watch_enabled=bool(args.post_watch_enabled),
        post_watch_name=str(args.post_watch_name),
    )

    actions = []
    if args.apply:
        actions = apply_remediation(
            status=status,
            command_specs=command_specs,
            repo_root=repo_root,
            refresh_live_once=bool(args.refresh_live_once),
            args=args,
        )
        status = build_status(
            repo_root=repo_root,
            dataset=repo_root / args.dataset,
            baseline=repo_root / args.baseline,
            agent=repo_root / args.agent,
            runner_state_path=repo_root / args.runner_state,
            pipeline_pid_path=repo_root / args.pipeline_pid,
            live_pid_path=repo_root / args.live_pid,
            round6_pid_path=repo_root / args.round6_pid,
            pipeline_log=repo_root / args.pipeline_log,
            live_log=repo_root / args.live_log,
            round6_log=repo_root / args.round6_log,
            report_dir=repo_root / args.report_dir,
            stall_seconds=int(args.stall_seconds),
            command_specs=command_specs,
            live_status_md=repo_root / args.live_status_md,
            snapshot_history_md=repo_root / args.snapshot_history_md,
            guardian_events_path=repo_root / args.guardian_events,
            post_watch_enabled=bool(args.post_watch_enabled),
            post_watch_name=str(args.post_watch_name),
        )
    status["guardian"] = {
        "mode": "apply" if args.apply else "observe",
        "actions_applied": actions,
        "loop": bool(args.loop),
        "poll_seconds": int(args.poll_seconds),
    }

    bundle = build_bundle(status)
    repo_root = Path(__file__).resolve().parents[1]
    write_json(repo_root / args.status_out, status)
    write_json(repo_root / args.bundle_out, bundle)
    write_reentry_prompt(repo_root / args.prompt_out, bundle)
    log_guardian_event(repo_root, status)
    return status


def main():
    parser = argparse.ArgumentParser(description="Guardian for the canonical experiment, with resume-aware status, handoff bundle, and auto-restart.")
    parser.add_argument("--dataset", default="data/main_eval/longbench_3tasks_test.jsonl")
    parser.add_argument("--baseline", default="results/baseline_rag_formal_anchor_4b_canonical.jsonl")
    parser.add_argument("--agent", default="results/edge_agent_formal_fast_canonical_s42.jsonl")
    parser.add_argument("--baseline_shard_dir", default="results/_sharded/baseline_rag_formal_anchor_4b_canonical")
    parser.add_argument("--baseline_state", default="results/_sharded/baseline_rag_formal_anchor_4b_canonical/_runner_state.json")
    parser.add_argument("--agent_shard_dir", default="results/_sharded/edge_agent_formal_fast_canonical_s42")
    parser.add_argument("--runner_state", default="results/_sharded/edge_agent_formal_fast_canonical_s42/_runner_state.json")
    parser.add_argument("--pipeline_pid", default="logs/canonical_single_seed_pipeline/pid.txt")
    parser.add_argument("--live_pid", default="logs/canonical_live_status/pid.txt")
    parser.add_argument("--round6_pid", default="logs/round6_monitor_after_canonical/pid.txt")
    parser.add_argument("--pipeline_log", default="logs/canonical_single_seed_pipeline/stdout.log")
    parser.add_argument("--pipeline_stderr", default="logs/canonical_single_seed_pipeline/stderr.log")
    parser.add_argument("--live_log", default="logs/canonical_live_status/stdout.log")
    parser.add_argument("--live_stderr", default="logs/canonical_live_status/stderr.log")
    parser.add_argument("--round6_log", default="logs/round6_monitor_after_canonical/stdout.log")
    parser.add_argument("--round6_stderr", default="logs/round6_monitor_after_canonical/stderr.log")
    parser.add_argument("--report_dir", default="report/formal_fast_canonical_s42_current")
    parser.add_argument("--live_status_json", default="report_live/canonical_live_status.json")
    parser.add_argument("--live_status_md", default="docs/33_canonical_live_status.md")
    parser.add_argument("--snapshot_history_md", default="docs/34_canonical_analysis_snapshots.md")
    parser.add_argument("--live_snapshot_state_json", default="report_live/canonical_snapshot_state.json")
    parser.add_argument("--guardian_events", default="logs/canonical_guardian/events.jsonl")
    parser.add_argument("--pipeline_script", default="scripts/cmd/run_canonical_single_seed_pipeline.ps1")
    parser.add_argument("--pipeline_dataset", default="data/main_eval/longbench_3tasks_test.jsonl")
    parser.add_argument("--pipeline_baseline_out", default="results/baseline_rag_formal_anchor_4b_canonical.jsonl")
    parser.add_argument("--pipeline_agent_config", default="configs/agent_qwen3_4b_fast.yaml")
    parser.add_argument("--pipeline_agent_out", default="results/edge_agent_formal_fast_canonical_s42.jsonl")
    parser.add_argument("--pipeline_report_dir", default="report/formal_fast_canonical_s42_current")
    parser.add_argument("--pipeline_run_tag", default="formal_fast_canonical_s42_current")
    parser.add_argument("--pipeline_shard_size", type=int, default=170)
    parser.add_argument("--pipeline_concurrency", type=int, default=2)
    parser.add_argument("--pipeline_seed", type=int, default=42)
    parser.add_argument("--pipeline_poll_seconds", type=int, default=60)
    parser.add_argument("--pipeline_stall_seconds", type=int, default=1800)
    parser.add_argument("--pipeline_max_retries_per_shard", type=int, default=2)
    parser.add_argument("--post_watch_enabled", action="store_true")
    parser.add_argument("--post_watch_name", default="round6 watcher")
    parser.add_argument("--post_watch_script", default="scripts/cmd/run_round6_monitor_after_canonical.ps1")
    parser.add_argument("--post_watch_report_dir", default="report/formal_fast_canonical_s42_current")
    parser.add_argument("--post_watch_poll_seconds", type=int, default=120)
    parser.add_argument("--post_watch_seed", type=int, default=42)
    parser.add_argument("--stall_seconds", type=int, default=1800)
    parser.add_argument("--poll_seconds", type=int, default=120)
    parser.add_argument("--live_poll_seconds", type=int, default=120)
    parser.add_argument("--status_out", default="report_live/canonical_supervisor_status.json")
    parser.add_argument("--bundle_out", default="report_live/codex_incident_bundle.json")
    parser.add_argument("--prompt_out", default="docs/35_codex_reentry_prompt.md")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--stop_when_done", action="store_true")
    parser.add_argument("--refresh_live_once", action="store_true")
    args = parser.parse_args()

    command_specs = build_command_specs(
        repo_root=Path(__file__).resolve().parents[1],
        args=args,
    )

    while True:
        status = run_cycle(args, command_specs)
        print(
            "guardian cycle: stage={} anomalies={} warnings={} effective_agent_lines={}".format(
                status["stage"],
                len(status["anomalies"]),
                len(status["warnings"]),
                status["progress"]["effective_agent_lines"],
            ),
            flush=True,
        )
        if not args.loop:
            return
        if args.stop_when_done and status["progress"]["metrics_ready"]:
            return
        time.sleep(max(10, int(args.poll_seconds)))


if __name__ == "__main__":
    main()
