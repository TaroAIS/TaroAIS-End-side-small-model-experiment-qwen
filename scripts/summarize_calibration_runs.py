#!/usr/bin/env python3
import argparse
import csv
import json
import math
from pathlib import Path


def _read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _safe_float(value):
    try:
        return float(value)
    except Exception:
        return 0.0


def _mean(values):
    if not values:
        return 0.0
    return sum(values) / float(len(values))


def _std(values):
    if len(values) <= 1:
        return 0.0
    mu = _mean(values)
    var = sum((x - mu) ** 2 for x in values) / float(len(values) - 1)
    return math.sqrt(max(0.0, var))


def _ci95(values):
    n = len(values)
    if n <= 1:
        return 0.0
    return 1.96 * _std(values) / math.sqrt(float(n))


def main():
    parser = argparse.ArgumentParser(description="Summarize threshold calibration seed runs.")
    parser.add_argument("--input_root", required=True)
    parser.add_argument("--out_dir", required=True)
    args = parser.parse_args()

    input_root = Path(args.input_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    per_method = {}
    for metrics_path in sorted(input_root.glob("seed_*/metrics_table.csv")):
        for row in _read_csv(metrics_path):
            method = row.get("method", "")
            if not method:
                continue
            entry = per_method.setdefault(
                method,
                {
                    "f1": [],
                    "p95_latency_ms": [],
                    "avg_steps": [],
                    "avg_retrieval": [],
                    "oom_count": [],
                },
            )
            entry["f1"].append(_safe_float(row.get("f1", 0.0)))
            entry["p95_latency_ms"].append(_safe_float(row.get("p95_latency_ms", 0.0)))
            entry["avg_steps"].append(_safe_float(row.get("avg_steps", 0.0)))
            entry["avg_retrieval"].append(_safe_float(row.get("avg_retrieval", 0.0)))
            entry["oom_count"].append(_safe_float(row.get("oom_count", 0.0)))

    summary_rows = []
    for method, metrics in sorted(per_method.items()):
        summary_rows.append(
            {
                "method": method,
                "n_seeds": len(metrics["f1"]),
                "mean_f1": _mean(metrics["f1"]),
                "ci95_f1": _ci95(metrics["f1"]),
                "mean_p95_latency_ms": _mean(metrics["p95_latency_ms"]),
                "ci95_p95_latency_ms": _ci95(metrics["p95_latency_ms"]),
                "mean_avg_steps": _mean(metrics["avg_steps"]),
                "mean_avg_retrieval": _mean(metrics["avg_retrieval"]),
                "oom_sum": int(sum(metrics["oom_count"])),
            }
        )

    summary_path = out_dir / "calibration_method_summary.csv"
    with open(summary_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "method",
                "n_seeds",
                "mean_f1",
                "ci95_f1",
                "mean_p95_latency_ms",
                "ci95_p95_latency_ms",
                "mean_avg_steps",
                "mean_avg_retrieval",
                "oom_sum",
            ],
        )
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(row)

    recommendation = {
        "generated_from": str(input_root),
        "summary_csv": str(summary_path),
        "notes": [
            "Use baseline_rag / baseline_budget_matched / baseline_single_round_strong / edge-agent variants to recalibrate canonical thresholds.",
            "Current repository thresholds remain frozen in data/manifests/threshold_calibration_policy.json until this calibration report is reviewed.",
        ],
    }
    (out_dir / "threshold_recommendation.json").write_text(
        json.dumps(recommendation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
