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


def _safe_int(v):
    try:
        return int(v)
    except Exception:
        return 0


def _evaluate_rows(gold_map, pred_rows, run_mode):
    rows = []
    for row in pred_rows:
        sid = row.get("id", "")
        gold_info = gold_map.get(sid, {})
        gold = gold_info.get("answer", row.get("gold", ""))
        task = gold_info.get("task", "unknown")
        pred = row.get("pred", "")

        em, f1 = best_over_gold(pred, gold)
        lt = row.get("latency_ms", {})
        gm = row.get("gpu_mem_mb", {})
        backend_mode = str(row.get("backend_mode", "unknown"))
        if run_mode == "formal" and backend_mode != "real":
            raise RuntimeError(
                "Formal mode requires backend_mode=real. got id={} backend_mode={}".format(
                    sid, backend_mode
                )
            )

        rows.append(
            {
                "id": sid,
                "task": task,
                "pred": pred,
                "gold": gold,
                "em": float(em),
                "f1": float(f1),
                "n_steps": _safe_int(row.get("n_steps", 1)),
                "n_retrieval": _safe_int(row.get("n_retrieval", 0)),
                "latency_total": _safe_float(lt.get("total", 0.0)),
                "gpu_peak": _safe_float(gm.get("peak", 0.0)),
                "gpu_mean": _safe_float(gm.get("mean", 0.0)),
                "prompt_tokens_total": _safe_float(row.get("prompt_tokens_total", 0.0)),
                "completion_tokens_total": _safe_float(row.get("completion_tokens_total", 0.0)),
                "retrieved_chunks_total": _safe_float(row.get("retrieved_chunks_total", 0.0)),
                "error_count": _safe_int(row.get("error_count", 0)),
                "backend_mode": backend_mode,
            }
        )
    return rows


def _aggregate_rows(rows):
    n = float(len(rows)) if rows else 1.0
    backend_modes = sorted(set([r.get("backend_mode", "unknown") for r in rows]))
    if len(backend_modes) == 1:
        backend_mode = backend_modes[0]
    elif len(backend_modes) == 0:
        backend_mode = "unknown"
    else:
        backend_mode = "mixed"

    lat = [r.get("latency_total", 0.0) for r in rows]
    gpu_peak = [r.get("gpu_peak", 0.0) for r in rows]
    gpu_mean = [r.get("gpu_mean", 0.0) for r in rows]

    return {
        "backend_mode": backend_mode,
        "n_samples": int(len(rows)),
        "em": sum([r.get("em", 0.0) for r in rows]) / n,
        "f1": sum([r.get("f1", 0.0) for r in rows]) / n,
        "avg_steps": sum([r.get("n_steps", 0) for r in rows]) / n,
        "avg_retrieval": sum([r.get("n_retrieval", 0) for r in rows]) / n,
        "avg_retrieved_chunks_total": sum([r.get("retrieved_chunks_total", 0.0) for r in rows]) / n,
        "avg_prompt_tokens_total": sum([r.get("prompt_tokens_total", 0.0) for r in rows]) / n,
        "avg_completion_tokens_total": sum([r.get("completion_tokens_total", 0.0) for r in rows]) / n,
        "p50_latency_ms": percentile(lat, 50),
        "p95_latency_ms": percentile(lat, 95),
        "gpu_peak_mb": max(gpu_peak) if gpu_peak else 0.0,
        "gpu_mean_mb": sum(gpu_mean) / n,
        "oom_count": int(sum([1 for r in rows if int(r.get("error_count", 0)) > 0])),
    }


def _group_rows_by_task(rows):
    groups = {}
    for r in rows:
        task = r.get("task", "unknown")
        if task not in groups:
            groups[task] = []
        groups[task].append(r)
    return groups


def _key_task_summary(method, run_tag, rows, task_metrics, key_tasks, key_agg):
    key_set = set(key_tasks or [])
    filtered_tasks = [t for t in sorted(task_metrics.keys()) if t in key_set]

    if key_agg == "micro":
        filtered_rows = [r for r in rows if r.get("task", "") in key_set]
        agg = _aggregate_rows(filtered_rows)
        agg["n_tasks"] = len(sorted(set([r.get("task", "") for r in filtered_rows])))
    else:
        # macro across tasks (equal task weight).
        if not filtered_tasks:
            agg = _aggregate_rows([])
            agg["n_tasks"] = 0
        else:
            per_task_aggs = [task_metrics[t] for t in filtered_tasks]
            n = float(len(per_task_aggs))
            mixed_backend = sorted(set([x.get("backend_mode", "unknown") for x in per_task_aggs]))
            if len(mixed_backend) == 1:
                backend_mode = mixed_backend[0]
            else:
                backend_mode = "mixed"
            agg = {
                "backend_mode": backend_mode,
                "n_samples": int(sum([x.get("n_samples", 0) for x in per_task_aggs])),
                "em": sum([x.get("em", 0.0) for x in per_task_aggs]) / n,
                "f1": sum([x.get("f1", 0.0) for x in per_task_aggs]) / n,
                "avg_steps": sum([x.get("avg_steps", 0.0) for x in per_task_aggs]) / n,
                "avg_retrieval": sum([x.get("avg_retrieval", 0.0) for x in per_task_aggs]) / n,
                "avg_retrieved_chunks_total": sum([x.get("avg_retrieved_chunks_total", 0.0) for x in per_task_aggs]) / n,
                "avg_prompt_tokens_total": sum([x.get("avg_prompt_tokens_total", 0.0) for x in per_task_aggs]) / n,
                "avg_completion_tokens_total": sum([x.get("avg_completion_tokens_total", 0.0) for x in per_task_aggs]) / n,
                "p50_latency_ms": sum([x.get("p50_latency_ms", 0.0) for x in per_task_aggs]) / n,
                "p95_latency_ms": sum([x.get("p95_latency_ms", 0.0) for x in per_task_aggs]) / n,
                "gpu_peak_mb": sum([x.get("gpu_peak_mb", 0.0) for x in per_task_aggs]) / n,
                "gpu_mean_mb": sum([x.get("gpu_mean_mb", 0.0) for x in per_task_aggs]) / n,
                "oom_count": int(sum([x.get("oom_count", 0) for x in per_task_aggs])),
                "n_tasks": len(filtered_tasks),
            }

    out = {
        "method": method,
        "run_tag": run_tag,
        "key_tasks": "|".join(key_tasks),
        "key_agg": key_agg,
        "n_tasks": int(agg.get("n_tasks", 0)),
        "n_samples": int(agg.get("n_samples", 0)),
        "backend_mode": agg.get("backend_mode", "unknown"),
        "em": agg.get("em", 0.0),
        "f1": agg.get("f1", 0.0),
        "avg_steps": agg.get("avg_steps", 0.0),
        "avg_retrieval": agg.get("avg_retrieval", 0.0),
        "avg_retrieved_chunks_total": agg.get("avg_retrieved_chunks_total", 0.0),
        "avg_prompt_tokens_total": agg.get("avg_prompt_tokens_total", 0.0),
        "avg_completion_tokens_total": agg.get("avg_completion_tokens_total", 0.0),
        "p50_latency_ms": agg.get("p50_latency_ms", 0.0),
        "p95_latency_ms": agg.get("p95_latency_ms", 0.0),
        "gpu_peak_mb": agg.get("gpu_peak_mb", 0.0),
        "gpu_mean_mb": agg.get("gpu_mean_mb", 0.0),
        "oom_count": int(agg.get("oom_count", 0)),
    }
    return out


def _write_placeholder_figures(out_dir):
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


def _save_figures(df, out_dir, run_mode, warnings):
    ensure_dir(out_dir)
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        if run_mode == "formal":
            raise RuntimeError("matplotlib is required in formal mode: {}".format(exc))
        _write_placeholder_figures(out_dir)
        warnings.append("matplotlib unavailable, wrote placeholder figures.")
        return

    plt.figure(figsize=(8, 4))
    plt.bar(df["method"], df["f1"], color="#2E7D32")
    for i, v in enumerate(df["f1"].tolist()):
        plt.text(i, v + 0.01, "{:.2f}".format(v), ha="center", fontsize=9)
    plt.ylabel("F1")
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.savefig(Path(out_dir) / "accuracy_bar.png", dpi=150)
    plt.close()

    plt.figure(figsize=(6, 5))
    plt.scatter(df["p95_latency_ms"], df["f1"], c="#1565C0")
    for _, row in df.iterrows():
        plt.text(row["p95_latency_ms"], row["f1"], row["method"], fontsize=8)
    plt.xlabel("P95 latency (ms)")
    plt.ylabel("F1")
    plt.tight_layout()
    plt.savefig(Path(out_dir) / "cost_effect_curve.png", dpi=150)
    plt.close()

    plt.figure(figsize=(6, 5))
    plt.scatter(df["avg_retrieval"], df["f1"], c="#EF6C00")
    for _, row in df.iterrows():
        plt.text(row["avg_retrieval"], row["f1"], row["method"], fontsize=8)
    plt.xlabel("avg_retrieval")
    plt.ylabel("F1")
    plt.tight_layout()
    plt.savefig(Path(out_dir) / "retrieval_effect_curve.png", dpi=150)
    plt.close()

    plt.figure(figsize=(8, 4))
    plt.plot(df["method"], df["gpu_peak_mb"], marker="o", label="peak")
    plt.plot(df["method"], df["gpu_mean_mb"], marker="s", label="mean")
    plt.ylabel("GPU mem (MB)")
    plt.xticks(rotation=15)
    plt.legend()
    plt.tight_layout()
    plt.savefig(Path(out_dir) / "gpu_mem_curve.png", dpi=150)
    plt.close()


def _to_dataframe(rows, run_mode):
    try:
        import pandas as pd
    except Exception as exc:
        if run_mode == "formal":
            raise RuntimeError("pandas is required in formal mode: {}".format(exc))
        pd = None
    if pd is not None:
        return pd.DataFrame(rows), pd

    class _MiniDF(object):
        def __init__(self, rows_in):
            self.rows = rows_in

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

    return _MiniDF(rows), None


def _save_table(rows, path, order, run_mode):
    df, pd = _to_dataframe(rows, run_mode)
    if pd is not None:
        for col in order:
            if col not in df.columns:
                df[col] = 0
        df = df[order]
        df.to_csv(path, index=False)
        return df
    normalized = []
    for r in rows:
        x = {}
        for col in order:
            x[col] = r.get(col, 0)
        normalized.append(x)
    mdf, _ = _to_dataframe(normalized, "smoke")
    mdf.to_csv(path, index=False)
    return mdf


def main():
    parser = argparse.ArgumentParser(description="Evaluate prediction jsonl files and generate report.")
    parser.add_argument("--gold", required=True)
    parser.add_argument("--pred", nargs="+", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--run_mode", choices=["smoke", "formal"], default="formal")
    parser.add_argument("--task_breakdown", action="store_true", default=True)
    parser.add_argument("--no_task_breakdown", dest="task_breakdown", action="store_false")
    parser.add_argument("--key_tasks", nargs="+", default=["multi_doc_qa", "code_qa"])
    parser.add_argument("--key_agg", choices=["macro", "micro"], default="macro")
    parser.add_argument("--run_tag", default="")
    args = parser.parse_args()

    ensure_dir(args.out_dir)
    gold_rows = load_jsonl(args.gold)
    validate_records(gold_rows, schema_path("dataset.schema.json"), context_prefix="gold")
    gold_map = {
        r.get("id", ""): {
            "answer": r.get("answer", ""),
            "task": r.get("task", "unknown"),
        }
        for r in gold_rows
    }

    metrics_rows = []
    all_error_cases = []
    ablation_rows = []
    task_metrics_rows = []
    key_task_summary_rows = []

    for pred_path in args.pred:
        pred_rows = load_jsonl(pred_path)
        validate_records(pred_rows, schema_path("result.schema.json"), context_prefix="pred")
        method = _method_name(pred_path)

        row_level = _evaluate_rows(gold_map, pred_rows, args.run_mode)
        mt = _aggregate_rows(row_level)

        row = {
            "method": method,
            "backend_mode": mt["backend_mode"],
            "em": mt["em"],
            "f1": mt["f1"],
            "avg_steps": mt["avg_steps"],
            "avg_retrieval": mt["avg_retrieval"],
            "avg_retrieved_chunks_total": mt["avg_retrieved_chunks_total"],
            "avg_prompt_tokens_total": mt["avg_prompt_tokens_total"],
            "avg_completion_tokens_total": mt["avg_completion_tokens_total"],
            "p50_latency_ms": mt["p50_latency_ms"],
            "p95_latency_ms": mt["p95_latency_ms"],
            "gpu_peak_mb": mt["gpu_peak_mb"],
            "gpu_mean_mb": mt["gpu_mean_mb"],
            "oom_count": mt["oom_count"],
        }
        metrics_rows.append(row)

        for r in row_level:
            if r.get("f1", 0.0) < 0.2:
                all_error_cases.append(
                    {
                        "id": r.get("id", ""),
                        "pred": r.get("pred", ""),
                        "gold": r.get("gold", ""),
                        "f1": r.get("f1", 0.0),
                        "method": method,
                    }
                )

        if args.task_breakdown:
            grouped = _group_rows_by_task(row_level)
            task_agg = {}
            for task in sorted(grouped.keys()):
                agg = _aggregate_rows(grouped[task])
                task_agg[task] = agg
                task_metrics_rows.append(
                    {
                        "method": method,
                        "run_tag": args.run_tag,
                        "task": task,
                        "n_samples": agg.get("n_samples", 0),
                        "backend_mode": agg.get("backend_mode", "unknown"),
                        "em": agg.get("em", 0.0),
                        "f1": agg.get("f1", 0.0),
                        "avg_steps": agg.get("avg_steps", 0.0),
                        "avg_retrieval": agg.get("avg_retrieval", 0.0),
                        "avg_retrieved_chunks_total": agg.get("avg_retrieved_chunks_total", 0.0),
                        "avg_prompt_tokens_total": agg.get("avg_prompt_tokens_total", 0.0),
                        "avg_completion_tokens_total": agg.get("avg_completion_tokens_total", 0.0),
                        "p50_latency_ms": agg.get("p50_latency_ms", 0.0),
                        "p95_latency_ms": agg.get("p95_latency_ms", 0.0),
                        "gpu_peak_mb": agg.get("gpu_peak_mb", 0.0),
                        "gpu_mean_mb": agg.get("gpu_mean_mb", 0.0),
                        "oom_count": int(agg.get("oom_count", 0)),
                    }
                )

            key_task_summary_rows.append(
                _key_task_summary(
                    method=method,
                    run_tag=args.run_tag,
                    rows=row_level,
                    task_metrics=task_agg,
                    key_tasks=args.key_tasks,
                    key_agg=args.key_agg,
                )
            )

        if any(
            k in method
            for k in [
                "iterative_off",
                "memory_sliding",
                "refine_gate_relaxed",
                "budget_tight",
                "forced_retrieve_off",
                "early_stop_off",
                "think_off",
                "inj_defense_off",
            ]
        ):
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

    metrics_order = [
        "method",
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
    df = _save_table(metrics_rows, Path(args.out_dir) / "metrics_table.csv", metrics_order, args.run_mode)

    if args.task_breakdown:
        task_order = [
            "method",
            "run_tag",
            "task",
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
        _save_table(task_metrics_rows, Path(args.out_dir) / "task_metrics.csv", task_order, args.run_mode)

        key_order = [
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
        _save_table(
            key_task_summary_rows,
            Path(args.out_dir) / "key_task_summary.csv",
            key_order,
            args.run_mode,
        )

    if ablation_rows:
        ab_order = [
            "variant",
            "description",
            "em",
            "f1",
            "avg_retrieval",
            "p95_latency_ms",
            "gpu_peak_mb",
        ]
        _save_table(ablation_rows, Path(args.out_dir) / "ablation_table.csv", ab_order, args.run_mode)

    if all_error_cases:
        dump_jsonl(Path(args.out_dir) / "error_cases.jsonl", all_error_cases)

    warnings = []
    _save_figures(df, args.out_dir, args.run_mode, warnings)
    if warnings:
        (Path(args.out_dir) / "_warnings.txt").write_text("\n".join(warnings) + "\n", encoding="utf-8")
    print("report generated at {}".format(args.out_dir))


if __name__ == "__main__":
    main()
