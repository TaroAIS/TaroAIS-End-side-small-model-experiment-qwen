#!/usr/bin/env python3
import argparse
import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


RE_RANGE = re.compile(r"_(\d{4})_(\d{4})\.jsonl$")


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_tail(path: Path, lines: int = 20) -> List[str]:
    text = read_text(path)
    return text.splitlines()[-lines:]


def load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def load_csv_rows(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parse_shard_dir(shard_dir: Path) -> Tuple[List[dict], int]:
    shards = []
    total_lines = 0
    if not shard_dir.exists():
        return shards, total_lines

    for path in sorted(shard_dir.glob("*.jsonl")):
        lines = count_lines(path)
        total_lines += lines
        start = None
        end = None
        match = RE_RANGE.search(path.name)
        if match:
            start = int(match.group(1))
            end = int(match.group(2))
        shards.append(
            {
                "name": path.name,
                "start": start,
                "end": end,
                "lines": lines,
                "last_write_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(
                    timespec="seconds"
                ),
            }
        )
    return shards, total_lines


def compute_canonical_summary(report_dir: Path) -> Optional[dict]:
    metrics_rows = load_csv_rows(report_dir / "metrics_table.csv")
    task_rows = load_csv_rows(report_dir / "task_metrics.csv")
    if not metrics_rows:
        return None

    baseline_row = next((r for r in metrics_rows if r["method"].startswith("baseline")), None)
    agent_row = next((r for r in metrics_rows if r["method"].startswith("edge_agent")), None)
    if not baseline_row or not agent_row:
        return None

    baseline_f1 = float(baseline_row["f1"])
    agent_f1 = float(agent_row["f1"])
    baseline_p95 = float(baseline_row["p95_latency_ms"])
    agent_p95 = float(agent_row["p95_latency_ms"])
    p95_ratio = (agent_p95 / baseline_p95) if baseline_p95 > 0 else 0.0

    task_breakdown = {}
    for task in ["single_doc_qa", "multi_doc_qa", "code_qa"]:
        row = next((r for r in task_rows if r["method"].startswith("edge_agent") and r["task"] == task), None)
        if row:
            task_breakdown[task] = {
                "f1": float(row["f1"]),
                "p95_latency_ms": float(row["p95_latency_ms"]),
            }

    return {
        "baseline_f1": baseline_f1,
        "agent_f1": agent_f1,
        "delta_f1": agent_f1 - baseline_f1,
        "p95_ratio": p95_ratio,
        "task_breakdown": task_breakdown,
    }


def compute_stage(total_rows: int, baseline_lines: int, agent_lines: int, canonical_summary: Optional[dict]) -> str:
    if canonical_summary is not None:
        return "canonical_report_ready"
    if agent_lines >= total_rows and total_rows > 0:
        return "agent_complete_pending_eval"
    if agent_lines > 0:
        return "agent_running"
    if baseline_lines >= total_rows and total_rows > 0:
        return "baseline_complete_waiting_agent"
    if baseline_lines > 0:
        return "baseline_running"
    return "waiting"


def extract_anomalies(agent_state: Optional[dict]) -> List[str]:
    if not agent_state:
        return []

    anomalies = []
    for job in agent_state.get("jobs", []):
        status = str(job.get("status", ""))
        note = str(job.get("note", ""))
        if status in {"retry_pending", "failed"}:
            anomalies.append(
                "{} status={} note={}".format(job.get("name", "unknown"), status, note or "-")
            )
        elif "stalled" in note or "stderr_growth" in note:
            anomalies.append("{} note={}".format(job.get("name", "unknown"), note))
    return anomalies


def compute_status(
    repo_root: Path,
    dataset: Path,
    final_baseline: Path,
    final_agent: Path,
    baseline_shard_dir: Path,
    agent_shard_dir: Path,
    baseline_state_path: Path,
    agent_state_path: Path,
    pipeline_log: Path,
    round6_log: Path,
    canonical_report_dir: Path,
):
    total_rows = count_lines(dataset)
    baseline_lines = count_lines(final_baseline)
    agent_lines = count_lines(final_agent)
    baseline_shards, baseline_shard_lines = parse_shard_dir(baseline_shard_dir)
    agent_shards, agent_shard_lines = parse_shard_dir(agent_shard_dir)
    baseline_state = load_json(baseline_state_path)
    agent_state = load_json(agent_state_path)
    canonical_summary = compute_canonical_summary(canonical_report_dir)
    anomalies = extract_anomalies(agent_state)
    stage = compute_stage(total_rows, baseline_lines, agent_lines or agent_shard_lines, canonical_summary)

    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": str(dataset.relative_to(repo_root)),
        "total_rows": total_rows,
        "stage": stage,
        "baseline": {
            "final_lines": baseline_lines,
            "progress": (baseline_lines / total_rows) if total_rows else 0.0,
            "state": baseline_state,
            "shards": baseline_shards,
            "shard_lines": baseline_shard_lines,
        },
        "agent": {
            "final_lines": agent_lines,
            "completed_shard_lines": agent_shard_lines,
            "progress": ((agent_lines or agent_shard_lines) / total_rows) if total_rows else 0.0,
            "state": agent_state,
            "shards": agent_shards,
        },
        "anomalies": anomalies,
        "pipeline_log_tail": read_tail(pipeline_log),
        "round6_log_tail": read_tail(round6_log),
        "canonical_summary": canonical_summary,
    }


def format_md(status: Dict) -> str:
    baseline = status["baseline"]
    agent = status["agent"]
    lines = [
        "# 33. Canonical Live Status",
        "",
        f"- updated_at: `{status['updated_at']}`",
        f"- stage: `{status['stage']}`",
        f"- dataset: `{status['dataset']}`",
        f"- total_rows: `{status['total_rows']}`",
        f"- baseline_final_lines: `{baseline['final_lines']} / {status['total_rows']}`",
        f"- agent_final_lines: `{agent['final_lines']} / {status['total_rows']}`",
        f"- agent_completed_shard_lines: `{agent['completed_shard_lines']} / {status['total_rows']}`",
        f"- anomaly_count: `{len(status['anomalies'])}`",
        "",
        "## Agent Runner",
        "",
    ]

    agent_state = agent.get("state") or {}
    if agent_state:
        lines.extend(
            [
                f"- completed_shards: `{agent_state.get('completed_shards', 0)}`",
                f"- running_shards: `{agent_state.get('running_shards', 0)}`",
                f"- pending_shards: `{agent_state.get('pending_shards', 0)}`",
                f"- failed_shards: `{agent_state.get('failed_shards', 0)}`",
                "",
                "| shard | status | attempts | out_lines | note |",
                "| --- | --- | ---: | ---: | --- |",
            ]
        )
        for job in agent_state.get("jobs", []):
            status_text = str(job.get("status", ""))
            if status_text in {"running", "retry_pending", "failed"}:
                lines.append(
                    "| `{}` | `{}` | {} | {} | `{}` |".format(
                        job.get("name", "unknown"),
                        status_text,
                        job.get("attempts", 0),
                        job.get("out_lines", 0),
                        str(job.get("note", "") or "-").replace("`", "'"),
                    )
                )
        if lines[-1] == "| --- | --- | ---: | ---: | --- |":
            lines.append("| - | - | - | - | - |")
    else:
        lines.append("- agent runner state: `unavailable`")

    lines.extend(
        [
            "",
            "## Anomalies",
            "",
        ]
    )
    if status["anomalies"]:
        for item in status["anomalies"]:
            lines.append(f"- {item}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Pipeline Log Tail",
            "",
            "```text",
            *status["pipeline_log_tail"],
            "```",
            "",
            "## Round 6 Watcher Tail",
            "",
            "```text",
            *status["round6_log_tail"],
            "```",
        ]
    )

    if status["canonical_summary"]:
        summary = status["canonical_summary"]
        lines.extend(
            [
                "",
                "## Canonical Summary",
                "",
                f"- baseline_f1: `{summary['baseline_f1']:.4f}`",
                f"- agent_f1: `{summary['agent_f1']:.4f}`",
                f"- delta_f1: `{summary['delta_f1']:.4f}`",
                f"- p95_ratio: `{summary['p95_ratio']:.4f}`",
                "",
                "| task | agent_f1 | agent_p95_latency_ms |",
                "| --- | ---: | ---: |",
            ]
        )
        for task in ["single_doc_qa", "multi_doc_qa", "code_qa"]:
            item = summary["task_breakdown"].get(task)
            if item:
                lines.append(f"| `{task}` | {item['f1']:.4f} | {item['p95_latency_ms']:.1f} |")
            else:
                lines.append(f"| `{task}` | - | - |")

    lines.append("")
    return "\n".join(lines)


def append_snapshot(status: Dict, snapshot_md: Path, snapshot_state_path: Path):
    summary_key = {
        "stage": status["stage"],
        "baseline_final_lines": status["baseline"]["final_lines"],
        "agent_final_lines": status["agent"]["final_lines"],
        "agent_completed_shard_lines": status["agent"]["completed_shard_lines"],
        "anomalies": status["anomalies"],
        "canonical_ready": status["canonical_summary"] is not None,
    }
    previous = load_json(snapshot_state_path) or {}
    if previous == summary_key:
        return

    snapshot_md.parent.mkdir(parents=True, exist_ok=True)
    snapshot_state_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "## {}".format(status["updated_at"]),
        "",
        "- stage: `{}`".format(status["stage"]),
        "- baseline_final_lines: `{}`".format(status["baseline"]["final_lines"]),
        "- agent_final_lines: `{}`".format(status["agent"]["final_lines"]),
        "- agent_completed_shard_lines: `{}`".format(status["agent"]["completed_shard_lines"]),
        "- anomalies: `{}`".format(len(status["anomalies"])),
    ]
    if status["anomalies"]:
        for item in status["anomalies"]:
            lines.append("- anomaly_detail: `{}`".format(item))
    if status["canonical_summary"]:
        lines.append("- canonical_agent_f1: `{:.4f}`".format(status["canonical_summary"]["agent_f1"]))
        lines.append("- canonical_delta_f1: `{:.4f}`".format(status["canonical_summary"]["delta_f1"]))
    lines.extend(["", ""])

    with snapshot_md.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))
    snapshot_state_path.write_text(json.dumps(summary_key, ensure_ascii=False, indent=2), encoding="utf-8")


def write_outputs(status: Dict, out_json: Path, out_md: Path, snapshot_md: Path, snapshot_state_path: Path):
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(format_md(status), encoding="utf-8")
    append_snapshot(status, snapshot_md, snapshot_state_path)


def main():
    parser = argparse.ArgumentParser(description="Continuously snapshot canonical experiment status.")
    parser.add_argument("--dataset", default="data/main_eval/longbench_3tasks_test.jsonl")
    parser.add_argument("--final_baseline", default="results/baseline_rag_formal_anchor_4b_canonical.jsonl")
    parser.add_argument("--final_agent", default="results/edge_agent_formal_fast_canonical_s42.jsonl")
    parser.add_argument("--baseline_shard_dir", default="results/_sharded/baseline_rag_formal_anchor_4b_canonical")
    parser.add_argument("--agent_shard_dir", default="results/_sharded/edge_agent_formal_fast_canonical_s42")
    parser.add_argument("--baseline_state", default="results/_sharded/baseline_rag_formal_anchor_4b_canonical/_runner_state.json")
    parser.add_argument("--agent_state", default="results/_sharded/edge_agent_formal_fast_canonical_s42/_runner_state.json")
    parser.add_argument("--pipeline_log", default="logs/canonical_single_seed_pipeline/stdout.log")
    parser.add_argument("--round6_log", default="logs/round6_monitor_after_canonical/stdout.log")
    parser.add_argument("--canonical_report_dir", default="report/formal_fast_canonical_s42_current")
    parser.add_argument("--out_json", default="report_live/canonical_live_status.json")
    parser.add_argument("--out_md", default="docs/33_canonical_live_status.md")
    parser.add_argument("--snapshot_md", default="docs/34_canonical_analysis_snapshots.md")
    parser.add_argument("--snapshot_state_json", default="report_live/canonical_snapshot_state.json")
    parser.add_argument("--poll_seconds", type=int, default=300)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--stop_when_done", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]

    while True:
        status = compute_status(
            repo_root=repo_root,
            dataset=repo_root / args.dataset,
            final_baseline=repo_root / args.final_baseline,
            final_agent=repo_root / args.final_agent,
            baseline_shard_dir=repo_root / args.baseline_shard_dir,
            agent_shard_dir=repo_root / args.agent_shard_dir,
            baseline_state_path=repo_root / args.baseline_state,
            agent_state_path=repo_root / args.agent_state,
            pipeline_log=repo_root / args.pipeline_log,
            round6_log=repo_root / args.round6_log,
            canonical_report_dir=repo_root / args.canonical_report_dir,
        )
        write_outputs(
            status=status,
            out_json=repo_root / args.out_json,
            out_md=repo_root / args.out_md,
            snapshot_md=repo_root / args.snapshot_md,
            snapshot_state_path=repo_root / args.snapshot_state_json,
        )
        if args.once:
            return
        if args.stop_when_done and status["canonical_summary"] is not None:
            return
        time.sleep(max(5, args.poll_seconds))


if __name__ == "__main__":
    main()
