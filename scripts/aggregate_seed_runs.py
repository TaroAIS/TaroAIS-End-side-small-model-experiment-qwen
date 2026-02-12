#!/usr/bin/env python3
import argparse
import csv
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.io import ensure_dir


def _safe_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def _safe_int(v):
    try:
        return int(v)
    except Exception:
        return 0


def _read_csv_rows(path):
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def _write_csv(path, rows, fieldnames):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _infer_run_tag(path, row):
    if row.get("run_tag"):
        return row.get("run_tag")
    p = Path(path)
    for part in reversed(p.parts):
        if part.startswith("seed_"):
            return part
    return p.parent.name or p.stem


def _group_by(rows, keys):
    out = {}
    for r in rows:
        k = tuple([r.get(x, "") for x in keys])
        if k not in out:
            out[k] = []
        out[k].append(r)
    return out


def _std_sample(values):
    if len(values) <= 1:
        return 0.0
    mean = sum(values) / float(len(values))
    var = sum([(x - mean) ** 2 for x in values]) / float(len(values) - 1)
    return math.sqrt(max(0.0, var))


def _t_crit_95(df):
    table = {
        1: 12.706,
        2: 4.303,
        3: 3.182,
        4: 2.776,
        5: 2.571,
        6: 2.447,
        7: 2.365,
        8: 2.306,
        9: 2.262,
        10: 2.228,
        15: 2.131,
        20: 2.086,
        30: 2.042,
        60: 2.000,
        120: 1.980,
    }
    if df <= 0:
        return 0.0
    if df in table:
        return table[df]
    if df > 120:
        return 1.960
    keys = sorted(table.keys())
    lo = keys[0]
    hi = keys[-1]
    for i in range(len(keys) - 1):
        a = keys[i]
        b = keys[i + 1]
        if a <= df <= b:
            lo = a
            hi = b
            break
    if lo == hi:
        return table[lo]
    t_lo = table[lo]
    t_hi = table[hi]
    ratio = (float(df) - float(lo)) / float(hi - lo)
    return t_lo + (t_hi - t_lo) * ratio


def _agg_stats(values):
    n = len(values)
    if n == 0:
        return {
            "n": 0,
            "mean": 0.0,
            "std": 0.0,
            "ci95_low": 0.0,
            "ci95_high": 0.0,
        }
    mean = sum(values) / float(n)
    std = _std_sample(values)
    if n <= 1:
        half = 0.0
    else:
        t = _t_crit_95(n - 1)
        half = t * std / math.sqrt(float(n))
    return {
        "n": n,
        "mean": mean,
        "std": std,
        "ci95_low": mean - half,
        "ci95_high": mean + half,
    }


def _build_key_summary_from_task_metrics(task_rows, key_tasks, key_agg):
    grouped = _group_by(task_rows, ["run_tag", "method"])
    out = []
    key_set = set(key_tasks)

    for (run_tag, method), rows in grouped.items():
        task_rows = [r for r in rows if r.get("task", "") in key_set]
        if not task_rows:
            continue

        if key_agg == "micro":
            total_n = sum([_safe_int(x.get("n_samples", 0)) for x in task_rows]) or 1

            def wavg(name):
                return sum(
                    [_safe_float(x.get(name, 0.0)) * _safe_int(x.get("n_samples", 0)) for x in task_rows]
                ) / float(total_n)

            row = {
                "method": method,
                "run_tag": run_tag,
                "key_tasks": "|".join(key_tasks),
                "key_agg": key_agg,
                "n_tasks": len(sorted(set([x.get("task", "") for x in task_rows]))),
                "n_samples": total_n,
                "backend_mode": "mixed",
                "em": wavg("em"),
                "f1": wavg("f1"),
                "avg_steps": wavg("avg_steps"),
                "avg_retrieval": wavg("avg_retrieval"),
                "avg_retrieved_chunks_total": wavg("avg_retrieved_chunks_total"),
                "avg_prompt_tokens_total": wavg("avg_prompt_tokens_total"),
                "avg_completion_tokens_total": wavg("avg_completion_tokens_total"),
                "p50_latency_ms": wavg("p50_latency_ms"),
                "p95_latency_ms": wavg("p95_latency_ms"),
                "gpu_peak_mb": wavg("gpu_peak_mb"),
                "gpu_mean_mb": wavg("gpu_mean_mb"),
                "oom_count": int(sum([_safe_int(x.get("oom_count", 0)) for x in task_rows])),
            }
        else:
            n = float(len(task_rows))

            def avg(name):
                return sum([_safe_float(x.get(name, 0.0)) for x in task_rows]) / n

            row = {
                "method": method,
                "run_tag": run_tag,
                "key_tasks": "|".join(key_tasks),
                "key_agg": key_agg,
                "n_tasks": len(sorted(set([x.get("task", "") for x in task_rows]))),
                "n_samples": int(sum([_safe_int(x.get("n_samples", 0)) for x in task_rows])),
                "backend_mode": "mixed",
                "em": avg("em"),
                "f1": avg("f1"),
                "avg_steps": avg("avg_steps"),
                "avg_retrieval": avg("avg_retrieval"),
                "avg_retrieved_chunks_total": avg("avg_retrieved_chunks_total"),
                "avg_prompt_tokens_total": avg("avg_prompt_tokens_total"),
                "avg_completion_tokens_total": avg("avg_completion_tokens_total"),
                "p50_latency_ms": avg("p50_latency_ms"),
                "p95_latency_ms": avg("p95_latency_ms"),
                "gpu_peak_mb": avg("gpu_peak_mb"),
                "gpu_mean_mb": avg("gpu_mean_mb"),
                "oom_count": int(sum([_safe_int(x.get("oom_count", 0)) for x in task_rows])),
            }
        out.append(row)
    return out


def _collect_long_records(metrics_rows, key_rows):
    records = []
    overall_metrics = [
        "em",
        "f1",
        "p95_latency_ms",
        "avg_retrieval",
        "avg_prompt_tokens_total",
        "avg_completion_tokens_total",
        "avg_retrieved_chunks_total",
    ]
    for row in metrics_rows:
        for m in overall_metrics:
            records.append(
                {
                    "scope": "overall",
                    "run_tag": row.get("run_tag", ""),
                    "method": row.get("method", ""),
                    "metric": m,
                    "value": _safe_float(row.get(m, 0.0)),
                }
            )

    key_metrics = [
        "em",
        "f1",
        "p95_latency_ms",
        "avg_retrieval",
        "avg_prompt_tokens_total",
        "avg_completion_tokens_total",
        "avg_retrieved_chunks_total",
    ]
    for row in key_rows:
        for m in key_metrics:
            records.append(
                {
                    "scope": "key_tasks",
                    "run_tag": row.get("run_tag", ""),
                    "method": row.get("method", ""),
                    "metric": m,
                    "value": _safe_float(row.get(m, 0.0)),
                }
            )
    return records


def _aggregate_long_records(records):
    grouped = _group_by(records, ["scope", "method", "metric"])
    out = []
    for (scope, method, metric), rows in sorted(grouped.items()):
        values = [_safe_float(x.get("value", 0.0)) for x in rows]
        stats = _agg_stats(values)
        out.append(
            {
                "scope": scope,
                "method": method,
                "metric": metric,
                "n": stats["n"],
                "mean": stats["mean"],
                "std": stats["std"],
                "ci95_low": stats["ci95_low"],
                "ci95_high": stats["ci95_high"],
            }
        )
    return out


def _find_mean(rows, scope, method, metric):
    for r in rows:
        if (
            r.get("scope", "") == scope
            and r.get("method", "") == method
            and r.get("metric", "") == metric
        ):
            return _safe_float(r.get("mean", 0.0))
    return None


def _decision_gate(agg_rows, baseline_method, agent_method, thresholds):
    baseline_f1 = _find_mean(agg_rows, "key_tasks", baseline_method, "f1")
    agent_f1 = _find_mean(agg_rows, "key_tasks", agent_method, "f1")
    baseline_latency = _find_mean(agg_rows, "key_tasks", baseline_method, "p95_latency_ms")
    agent_latency = _find_mean(agg_rows, "key_tasks", agent_method, "p95_latency_ms")
    baseline_retrieval = _find_mean(agg_rows, "key_tasks", baseline_method, "avg_retrieval")
    agent_retrieval = _find_mean(agg_rows, "key_tasks", agent_method, "avg_retrieval")

    reasons = []
    if baseline_f1 is None or agent_f1 is None:
        reasons.append("missing key-task f1 means for baseline/agent")
    if baseline_latency is None or agent_latency is None:
        reasons.append("missing key-task p95 latency means for baseline/agent")
    if baseline_retrieval is None or agent_retrieval is None:
        reasons.append("missing key-task avg_retrieval means for baseline/agent")

    delta_f1 = None
    latency_ratio = None
    retrieval_ratio = None

    if baseline_f1 is not None and agent_f1 is not None:
        delta_f1 = agent_f1 - baseline_f1
    if baseline_latency is not None and agent_latency is not None:
        if baseline_latency <= 0:
            latency_ratio = float("inf")
        else:
            latency_ratio = agent_latency / baseline_latency
    if baseline_retrieval is not None and agent_retrieval is not None:
        if baseline_retrieval <= 0:
            retrieval_ratio = float("inf")
        else:
            retrieval_ratio = agent_retrieval / baseline_retrieval

    checks = {
        "delta_f1_pass": False,
        "latency_ratio_pass": False,
        "retrieval_ratio_pass": False,
    }
    if delta_f1 is not None:
        checks["delta_f1_pass"] = delta_f1 >= thresholds["min_delta_f1"]
        if not checks["delta_f1_pass"]:
            reasons.append(
                "delta_f1 {:.6f} < min_delta_f1 {:.6f}".format(delta_f1, thresholds["min_delta_f1"])
            )
    if latency_ratio is not None:
        checks["latency_ratio_pass"] = latency_ratio <= thresholds["max_latency_ratio"]
        if not checks["latency_ratio_pass"]:
            reasons.append(
                "latency_ratio {:.6f} > max_latency_ratio {:.6f}".format(
                    latency_ratio, thresholds["max_latency_ratio"]
                )
            )
    if retrieval_ratio is not None:
        checks["retrieval_ratio_pass"] = retrieval_ratio <= thresholds["max_retrieval_ratio"]
        if not checks["retrieval_ratio_pass"]:
            reasons.append(
                "retrieval_ratio {:.6f} > max_retrieval_ratio {:.6f}".format(
                    retrieval_ratio, thresholds["max_retrieval_ratio"]
                )
            )

    passed = (
        len(reasons) == 0
        and checks["delta_f1_pass"]
        and checks["latency_ratio_pass"]
        and checks["retrieval_ratio_pass"]
    )
    return {
        "pass": bool(passed),
        "baseline_method": baseline_method,
        "agent_method": agent_method,
        "thresholds": thresholds,
        "observed": {
            "delta_f1_key_mean": delta_f1,
            "latency_ratio_key_mean": latency_ratio,
            "retrieval_ratio_key_mean": retrieval_ratio,
        },
        "checks": checks,
        "fail_reasons": reasons,
    }


def main():
    parser = argparse.ArgumentParser(description="Aggregate multi-seed reports and compute 95%CI + gate.")
    parser.add_argument("--metrics", nargs="+", required=True, help="metrics_table.csv paths from each seed run.")
    parser.add_argument("--task_metrics", nargs="*", default=[], help="optional task_metrics.csv paths.")
    parser.add_argument("--key_summary", nargs="*", default=[], help="optional key_task_summary.csv paths.")
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--key_tasks", nargs="+", default=["multi_doc_qa", "code_qa"])
    parser.add_argument("--key_agg", choices=["macro", "micro"], default="macro")
    parser.add_argument("--baseline_method", default="baseline_rag")
    parser.add_argument("--agent_method", default="edge_agent")
    parser.add_argument("--min_delta_f1", type=float, default=0.03)
    parser.add_argument("--max_latency_ratio", type=float, default=1.5)
    parser.add_argument("--max_retrieval_ratio", type=float, default=1.8)
    args = parser.parse_args()

    ensure_dir(args.out_dir)

    metrics_rows = []
    for p in args.metrics:
        for row in _read_csv_rows(p):
            x = dict(row)
            x["run_tag"] = _infer_run_tag(p, x)
            metrics_rows.append(x)

    key_rows = []
    if args.key_summary:
        for p in args.key_summary:
            for row in _read_csv_rows(p):
                x = dict(row)
                x["run_tag"] = _infer_run_tag(p, x)
                key_rows.append(x)
    elif args.task_metrics:
        task_rows = []
        for p in args.task_metrics:
            for row in _read_csv_rows(p):
                x = dict(row)
                x["run_tag"] = _infer_run_tag(p, x)
                task_rows.append(x)
        key_rows = _build_key_summary_from_task_metrics(
            task_rows=task_rows, key_tasks=args.key_tasks, key_agg=args.key_agg
        )

    if key_rows:
        key_summary_path = Path(args.out_dir) / "key_task_summary.csv"
        key_fields = [
            "method",
            "run_tag",
            "key_tasks",
            "key_agg",
            "n_tasks",
            "n_samples",
            "backend_mode",
            "em",
            "f1",
            "avg_steps",
            "avg_retrieval",
            "avg_retrieved_chunks_total",
            "avg_prompt_tokens_total",
            "avg_completion_tokens_total",
            "p50_latency_ms",
            "p95_latency_ms",
            "gpu_peak_mb",
            "gpu_mean_mb",
            "oom_count",
        ]
        _write_csv(key_summary_path, key_rows, key_fields)

    long_records = _collect_long_records(metrics_rows, key_rows)
    agg_rows = _aggregate_long_records(long_records)
    agg_fields = ["scope", "method", "metric", "n", "mean", "std", "ci95_low", "ci95_high"]
    _write_csv(Path(args.out_dir) / "seed_aggregate.csv", agg_rows, agg_fields)

    gate = _decision_gate(
        agg_rows=agg_rows,
        baseline_method=args.baseline_method,
        agent_method=args.agent_method,
        thresholds={
            "min_delta_f1": args.min_delta_f1,
            "max_latency_ratio": args.max_latency_ratio,
            "max_retrieval_ratio": args.max_retrieval_ratio,
        },
    )
    with open(Path(args.out_dir) / "decision_gate.json", "w", encoding="utf-8") as f:
        json.dump(gate, f, ensure_ascii=False, indent=2)

    print("seed aggregate -> {}".format(Path(args.out_dir) / "seed_aggregate.csv"))
    print("decision gate -> {}".format(Path(args.out_dir) / "decision_gate.json"))


if __name__ == "__main__":
    main()
