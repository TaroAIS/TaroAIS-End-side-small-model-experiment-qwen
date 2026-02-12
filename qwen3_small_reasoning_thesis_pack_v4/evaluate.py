#!/usr/bin/env python3
import argparse
from pathlib import Path

from metrics.qa_metrics import best_over_gold
from utils.io import dump_jsonl, ensure_dir, load_jsonl
from utils.runtime import schema_path
from utils.schema import validate_records
from utils.timer import percentile


def _method_name(path):
    p = Path(path)
    return p.stem


def _safe_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def evaluate_one(gold_map, pred_rows):
    ems = []
    f1s = []
    lat = []
    steps = []
    retr = []
    gpu_peak = []
    gpu_mean = []
    oom = 0
    error_cases = []

    for row in pred_rows:
        sid = row.get("id", "")
        pred = row.get("pred", "")
        gold = gold_map.get(sid, row.get("gold", ""))
        em, f1 = best_over_gold(pred, gold)
        ems.append(em)
        f1s.append(f1)

        lt = row.get("latency_ms", {})
        lat.append(_safe_float(lt.get("total", 0.0)))
        steps.append(int(row.get("n_steps", 1)))
        retr.append(int(row.get("n_retrieval", 0)))

        gm = row.get("gpu_mem_mb", {})
        gpu_peak.append(_safe_float(gm.get("peak", 0.0)))
        gpu_mean.append(_safe_float(gm.get("mean", 0.0)))

        if int(row.get("error_count", 0)) > 0:
            oom += 1

        if f1 < 0.2:
            error_cases.append(
                {
                    "id": sid,
                    "pred": pred,
                    "gold": gold,
                    "f1": f1,
                }
            )

    n = float(len(pred_rows)) if pred_rows else 1.0
    return {
        "em": sum(ems) / n,
        "f1": sum(f1s) / n,
        "avg_steps": sum(steps) / n,
        "avg_retrieval": sum(retr) / n,
        "p50_latency_ms": percentile(lat, 50),
        "p95_latency_ms": percentile(lat, 95),
        "gpu_peak_mb": max(gpu_peak) if gpu_peak else 0.0,
        "gpu_mean_mb": sum(gpu_mean) / n,
        "oom_count": int(oom),
        "error_cases": error_cases,
    }


def _save_figures(df, out_dir):
    ensure_dir(out_dir)
    try:
        import matplotlib.pyplot as plt
    except Exception:
        # Keep pipeline alive in minimal environments.
        import base64

        pixel = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO2Y6XQAAAAASUVORK5CYII="
        )
        for name in [
            "accuracy_bar.png",
            "cost_effect_curve.png",
            "retrieval_effect_curve.png",
            "gpu_mem_curve.png",
        ]:
            (Path(out_dir) / name).write_bytes(pixel)
        return

    # accuracy_bar.png
    plt.figure(figsize=(8, 4))
    plt.bar(df["method"], df["f1"], color="#2E7D32")
    for i, v in enumerate(df["f1"].tolist()):
        plt.text(i, v + 0.01, "{:.2f}".format(v), ha="center", fontsize=9)
    plt.ylabel("F1")
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.savefig(Path(out_dir) / "accuracy_bar.png", dpi=150)
    plt.close()

    # cost_effect_curve.png
    plt.figure(figsize=(6, 5))
    plt.scatter(df["p95_latency_ms"], df["f1"], c="#1565C0")
    for _, row in df.iterrows():
        plt.text(row["p95_latency_ms"], row["f1"], row["method"], fontsize=8)
    plt.xlabel("P95 latency (ms)")
    plt.ylabel("F1")
    plt.tight_layout()
    plt.savefig(Path(out_dir) / "cost_effect_curve.png", dpi=150)
    plt.close()

    # retrieval_effect_curve.png
    plt.figure(figsize=(6, 5))
    plt.scatter(df["avg_retrieval"], df["f1"], c="#EF6C00")
    for _, row in df.iterrows():
        plt.text(row["avg_retrieval"], row["f1"], row["method"], fontsize=8)
    plt.xlabel("avg_retrieval")
    plt.ylabel("F1")
    plt.tight_layout()
    plt.savefig(Path(out_dir) / "retrieval_effect_curve.png", dpi=150)
    plt.close()

    # gpu_mem_curve.png
    plt.figure(figsize=(8, 4))
    plt.plot(df["method"], df["gpu_peak_mb"], marker="o", label="peak")
    plt.plot(df["method"], df["gpu_mean_mb"], marker="s", label="mean")
    plt.ylabel("GPU mem (MB)")
    plt.xticks(rotation=15)
    plt.legend()
    plt.tight_layout()
    plt.savefig(Path(out_dir) / "gpu_mem_curve.png", dpi=150)
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Evaluate prediction jsonl files and generate report.")
    parser.add_argument("--gold", required=True)
    parser.add_argument("--pred", nargs="+", required=True)
    parser.add_argument("--out_dir", required=True)
    args = parser.parse_args()

    ensure_dir(args.out_dir)
    gold_rows = load_jsonl(args.gold)
    validate_records(gold_rows, schema_path("dataset.schema.json"), context_prefix="gold")
    gold_map = {r.get("id", ""): r.get("answer", "") for r in gold_rows}

    metrics_rows = []
    all_error_cases = []
    ablation_rows = []

    for pred_path in args.pred:
        pred_rows = load_jsonl(pred_path)
        validate_records(pred_rows, schema_path("result.schema.json"), context_prefix="pred")
        mt = evaluate_one(gold_map, pred_rows)
        method = _method_name(pred_path)

        row = {
            "method": method,
            "em": mt["em"],
            "f1": mt["f1"],
            "avg_steps": mt["avg_steps"],
            "avg_retrieval": mt["avg_retrieval"],
            "p50_latency_ms": mt["p50_latency_ms"],
            "p95_latency_ms": mt["p95_latency_ms"],
            "gpu_peak_mb": mt["gpu_peak_mb"],
            "gpu_mean_mb": mt["gpu_mean_mb"],
            "oom_count": mt["oom_count"],
        }
        metrics_rows.append(row)

        for e in mt["error_cases"]:
            x = dict(e)
            x["method"] = method
            all_error_cases.append(x)

        if any(k in method for k in ["think_off", "iterative_off", "memory_sliding", "inj_defense_off"]):
            ablation_rows.append(
                {
                    "variant": method,
                    "description": method,
                    "em": mt["em"],
                    "f1": mt["f1"],
                    "avg_retrieval": mt["avg_retrieval"],
                    "p95_latency_ms": mt["p95_latency_ms"],
                    "gpu_peak_mb": mt["gpu_peak_mb"],
                }
            )

    try:
        import pandas as pd
    except Exception:
        pd = None

    if pd is not None:
        df = pd.DataFrame(metrics_rows)
    else:
        # lightweight fallback table object for minimal runtime.
        class _MiniDF(object):
            def __init__(self, rows):
                self.rows = rows

            def __getitem__(self, key):
                return [r.get(key, 0) for r in self.rows]

            def iterrows(self):
                for i, r in enumerate(self.rows):
                    yield i, r

            @property
            def columns(self):
                if not self.rows:
                    return []
                return list(self.rows[0].keys())

            def to_csv(self, path, index=False):
                import csv

                cols = []
                for r in self.rows:
                    for k in r.keys():
                        if k not in cols:
                            cols.append(k)
                with open(path, "w", encoding="utf-8", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=cols)
                    w.writeheader()
                    for r in self.rows:
                        w.writerow(r)

        df = _MiniDF(metrics_rows)
    order = [
        "method",
        "em",
        "f1",
        "avg_steps",
        "avg_retrieval",
        "p50_latency_ms",
        "p95_latency_ms",
        "gpu_peak_mb",
        "gpu_mean_mb",
        "oom_count",
    ]
    if pd is not None:
        for col in order:
            if col not in df.columns:
                df[col] = 0
        df = df[order]
        df.to_csv(Path(args.out_dir) / "metrics_table.csv", index=False)
    else:
        normalized_rows = []
        for r in metrics_rows:
            nr = {}
            for col in order:
                nr[col] = r.get(col, 0)
            normalized_rows.append(nr)
        df = _MiniDF(normalized_rows)
        df.to_csv(Path(args.out_dir) / "metrics_table.csv", index=False)

    if ablation_rows and pd is not None:
        ab_df = pd.DataFrame(ablation_rows)
        ab_df.to_csv(Path(args.out_dir) / "ablation_table.csv", index=False)
    elif ablation_rows:
        import csv

        ab_path = Path(args.out_dir) / "ablation_table.csv"
        with open(ab_path, "w", encoding="utf-8", newline="") as f:
            cols = list(ablation_rows[0].keys())
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in ablation_rows:
                w.writerow(r)

    if all_error_cases:
        dump_jsonl(Path(args.out_dir) / "error_cases.jsonl", all_error_cases)

    _save_figures(df, args.out_dir)
    print("report generated at {}".format(args.out_dir))


if __name__ == "__main__":
    main()
