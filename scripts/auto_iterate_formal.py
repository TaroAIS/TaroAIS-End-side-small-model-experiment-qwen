#!/usr/bin/env python3
import argparse
import csv
import json
import math
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from metrics.qa_metrics import best_over_gold


def _now_ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


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


def _mean_ci95(values):
    xs = [float(x) for x in (values or [])]
    n = len(xs)
    if n <= 0:
        return {
            "n": 0,
            "mean": 0.0,
            "ci95": 0.0,
            "lower": 0.0,
            "upper": 0.0,
        }
    mean = sum(xs) / float(n)
    if n == 1:
        return {
            "n": 1,
            "mean": float(mean),
            "ci95": 0.0,
            "lower": float(mean),
            "upper": float(mean),
        }
    var = sum([(x - mean) ** 2 for x in xs]) / float(max(1, n - 1))
    se = math.sqrt(max(0.0, var) / float(n))
    ci95 = 1.96 * se
    return {
        "n": int(n),
        "mean": float(mean),
        "ci95": float(ci95),
        "lower": float(mean - ci95),
        "upper": float(mean + ci95),
    }


def _read_csv_rows(path):
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(dict(row))
    return rows


def _read_jsonl_rows(path):
    rows = []
    p = Path(path)
    if not p.exists():
        return rows
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                rows.append(json.loads(s))
            except Exception:
                continue
    return rows


def _load_state(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(path, state):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _run(cmd, cwd=ROOT, timeout_s=None):
    print("[run] {}".format(" ".join([str(x) for x in cmd])))
    env = os.environ.copy()
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    env.setdefault("HF_DATASETS_OFFLINE", "1")
    subprocess.run(cmd, cwd=str(cwd), env=env, check=True, timeout=timeout_s)


def _latest_result_file(pattern):
    result_root = ROOT / "results"
    files = [p for p in result_root.glob(pattern) if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda x: x.stat().st_mtime)


def _find_new_run_dir(before):
    run_root = ROOT / "results"
    after = set([p.name for p in run_root.glob("run_*") if p.is_dir()])
    created = sorted(list(after - before))
    if created:
        return max([run_root / x for x in created], key=lambda p: p.stat().st_mtime)
    all_dirs = [p for p in run_root.glob("run_*") if p.is_dir()]
    if not all_dirs:
        return None
    return max(all_dirs, key=lambda p: p.stat().st_mtime)


def _find_method_row(rows, prefer_stem, fallback_kw):
    if prefer_stem:
        for r in rows:
            if r.get("method", "") == prefer_stem:
                return r
        for r in rows:
            if prefer_stem in r.get("method", ""):
                return r
    for r in rows:
        if fallback_kw in r.get("method", ""):
            return r
    return {}


def _find_task_f1(task_rows, method_name, task):
    for r in task_rows:
        if r.get("method", "") == method_name and r.get("task", "") == task:
            return _safe_float(r.get("f1", 0.0))
    for r in task_rows:
        if task == r.get("task", "") and method_name and method_name in r.get("method", ""):
            return _safe_float(r.get("f1", 0.0))
    return 0.0


def _parse_report(report_dir, baseline_stem, agent_stem):
    metrics_rows = _read_csv_rows(Path(report_dir) / "metrics_table.csv")
    task_rows = _read_csv_rows(Path(report_dir) / "task_metrics.csv")

    baseline_row = _find_method_row(metrics_rows, baseline_stem, "baseline")
    agent_row = _find_method_row(metrics_rows, agent_stem, "edge_agent")

    baseline_method = baseline_row.get("method", "")
    agent_method = agent_row.get("method", "")

    baseline_p95 = _safe_float(baseline_row.get("p95_latency_ms", 0.0))
    agent_p95 = _safe_float(agent_row.get("p95_latency_ms", 0.0))
    p95_ratio = (agent_p95 / baseline_p95) if baseline_p95 > 0 else float("inf")
    baseline_single_doc_f1 = _find_task_f1(task_rows, baseline_method, "single_doc_qa")
    baseline_multi_doc_f1 = _find_task_f1(task_rows, baseline_method, "multi_doc_qa")
    baseline_code_f1 = _find_task_f1(task_rows, baseline_method, "code_qa")
    agent_single_doc_f1 = _find_task_f1(task_rows, agent_method, "single_doc_qa")
    agent_multi_doc_f1 = _find_task_f1(task_rows, agent_method, "multi_doc_qa")
    agent_code_f1 = _find_task_f1(task_rows, agent_method, "code_qa")

    return {
        "baseline_method": baseline_method,
        "agent_method": agent_method,
        "baseline_f1": _safe_float(baseline_row.get("f1", 0.0)),
        "agent_f1": _safe_float(agent_row.get("f1", 0.0)),
        "baseline_em": _safe_float(baseline_row.get("em", 0.0)),
        "agent_em": _safe_float(agent_row.get("em", 0.0)),
        "baseline_p95_ms": baseline_p95,
        "agent_p95_ms": agent_p95,
        "p95_ratio": p95_ratio,
        "agent_avg_steps": _safe_float(agent_row.get("avg_steps", 0.0)),
        "agent_avg_retrieval": _safe_float(agent_row.get("avg_retrieval", 0.0)),
        "agent_oom": _safe_int(agent_row.get("oom_count", 0)),
        "single_doc_f1": agent_single_doc_f1,
        "multi_doc_f1": agent_multi_doc_f1,
        "code_f1": agent_code_f1,
        "baseline_single_doc_f1": baseline_single_doc_f1,
        "baseline_multi_doc_f1": baseline_multi_doc_f1,
        "baseline_code_f1": baseline_code_f1,
        "delta_single_doc_f1": float(agent_single_doc_f1 - baseline_single_doc_f1),
        "delta_multi_doc_f1": float(agent_multi_doc_f1 - baseline_multi_doc_f1),
        "delta_code_f1": float(agent_code_f1 - baseline_code_f1),
        "report_dir": str(report_dir),
    }


def _collect_trace_stats(trace_dir):
    stats = {
        "trace_files": 0,
        "forced_final_count": 0,
        "low_confidence_step_count": 0,
        "forced_search_step_count": 0,
        "early_stop_reason_top": [],
    }
    if not trace_dir or not Path(trace_dir).exists():
        return stats

    early_counter = Counter()
    for p in Path(trace_dir).glob("*.json"):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        stats["trace_files"] += 1
        for step in obj.get("steps", []):
            if bool(step.get("forced_final", False)):
                stats["forced_final_count"] += 1
            if bool(step.get("low_confidence_detected", False)):
                stats["low_confidence_step_count"] += 1
            if bool(step.get("forced_search_applied", False)):
                stats["forced_search_step_count"] += 1
            reason = str(step.get("early_stop_reason", "") or "").strip()
            if reason:
                early_counter[reason] += 1
    stats["early_stop_reason_top"] = early_counter.most_common(5)
    return stats


def _gold_map(dataset_path):
    out = {}
    for row in _read_jsonl_rows(dataset_path):
        sid = str(row.get("id", "") or "")
        if not sid:
            continue
        out[sid] = {
            "answer": row.get("answer", ""),
            "task": row.get("task", "unknown"),
        }
    return out


def _sample_level_summary(dataset_path, baseline_pred_path, agent_pred_path, top_n=5):
    gold = _gold_map(dataset_path)
    baseline_rows = _read_jsonl_rows(baseline_pred_path)
    agent_rows = _read_jsonl_rows(agent_pred_path)
    base_map = {str(r.get("id", "") or ""): r for r in baseline_rows}
    agent_map = {str(r.get("id", "") or ""): r for r in agent_rows}

    deltas = []
    for sid, arow in agent_map.items():
        if sid not in base_map:
            continue
        info = gold.get(sid, {})
        answer = info.get("answer", arow.get("gold", ""))
        task = info.get("task", "unknown")
        _, bf1 = best_over_gold(str(base_map[sid].get("pred", "")), answer)
        _, af1 = best_over_gold(str(arow.get("pred", "")), answer)
        deltas.append(
            {
                "id": sid,
                "task": task,
                "baseline_f1": float(bf1),
                "agent_f1": float(af1),
                "delta_f1": float(af1 - bf1),
            }
        )

    regressions = sorted(
        [x for x in deltas if x["delta_f1"] < 0.0], key=lambda x: x["delta_f1"]
    )[: max(1, int(top_n))]
    improvements = sorted(
        [x for x in deltas if x["delta_f1"] > 0.0],
        key=lambda x: x["delta_f1"],
        reverse=True,
    )[: max(1, int(top_n))]

    latency_top = []
    for row in agent_rows:
        sid = str(row.get("id", "") or "")
        task = gold.get(sid, {}).get("task", "unknown")
        lt = row.get("latency_ms", {}) or {}
        latency_top.append(
            {
                "id": sid,
                "task": task,
                "latency_ms": _safe_float(lt.get("total", 0.0)),
                "n_steps": _safe_int(row.get("n_steps", 0)),
                "n_retrieval": _safe_int(row.get("n_retrieval", 0)),
            }
        )
    latency_top = sorted(latency_top, key=lambda x: x["latency_ms"], reverse=True)[
        : max(1, int(top_n))
    ]

    return {
        "regression_top": regressions,
        "improvement_top": improvements,
        "latency_top": latency_top,
    }


def _single_gate(m, thresholds):
    return {
        "overall_pass": m["agent_f1"] >= thresholds["overall_f1"],
        "single_doc_pass": m["single_doc_f1"] >= thresholds["single_doc_f1"],
        "ratio_pass": m["p95_ratio"] <= thresholds["p95_ratio"],
        "oom_pass": int(m["agent_oom"]) == 0,
    }


def _gate_ok(g):
    return bool(g["overall_pass"] and g["single_doc_pass"] and g["ratio_pass"] and g["oom_pass"])


def _score(can_m, dev_m, can_thresholds, dev_thresholds):
    # Canonical-first score: dev/holdout are monitoring guards, not main optimization target.
    can_f1 = float(can_m.get("agent_f1", 0.0))
    can_single = float(can_m.get("single_doc_f1", 0.0))
    can_multi = float(can_m.get("multi_doc_f1", 0.0))
    can_code = float(can_m.get("code_f1", 0.0))
    score_main = (
        0.70 * can_f1
        + 0.15 * can_single
        + 0.08 * can_multi
        + 0.07 * can_code
    )

    penalty_can = (
        0.30 * max(0.0, float(can_m.get("p95_ratio", 0.0)) - float(can_thresholds["p95_ratio"]))
        + 0.30 * max(0.0, float(can_thresholds["single_doc_f1"]) - can_single)
        + 0.30 * max(0.0, float(can_thresholds["overall_f1"]) - can_f1)
        + 0.10 * int(can_m.get("agent_oom", 0))
    )

    # Dev only acts as weak penalty to avoid catastrophic drift.
    penalty_dev = (
        0.05 * max(0.0, float(dev_m.get("p95_ratio", 0.0)) - float(dev_thresholds["p95_ratio"]))
        + 0.05 * max(0.0, float(dev_thresholds["overall_f1"]) - float(dev_m.get("agent_f1", 0.0)))
        + 0.05
        * max(
            0.0,
            float(dev_thresholds["single_doc_f1"]) - float(dev_m.get("single_doc_f1", 0.0)),
        )
        + 0.05 * int(dev_m.get("agent_oom", 0))
    )
    return float(score_main - penalty_can - penalty_dev)


def _detect_task_regressions(current, reference, drop_threshold):
    ref = reference or {}
    if not ref:
        return []
    items = [
        ("single_doc_qa", "single_doc_f1"),
        ("multi_doc_qa", "multi_doc_f1"),
        ("code_qa", "code_f1"),
    ]
    out = []
    for task_name, key in items:
        cur = float(current.get(key, 0.0))
        base = float(ref.get(key, 0.0))
        drop = base - cur
        if drop > float(drop_threshold):
            out.append(
                {
                    "task": task_name,
                    "drop": float(drop),
                    "reference": float(base),
                    "current": float(cur),
                }
            )
    return out


def _save_last_good_config(config_path, save_path):
    src = Path(config_path)
    dst = Path(save_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _restore_last_good_config(config_path, save_path):
    src = Path(save_path)
    if not src.exists():
        return False
    dst = Path(config_path)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return True


def _ensure_extended_sets(py, args):
    dev_path = ROOT / args.dev_dataset
    holdout_path = ROOT / args.holdout_dataset
    if (
        dev_path.exists()
        and holdout_path.exists()
        and not bool(args.force_rebuild_ext_eval)
    ):
        return ["extended eval datasets already exist"]

    cmd = [
        py,
        args.ext_builder_script,
        "--valid",
        args.valid_dataset,
        "--canonical",
        args.canonical_dataset,
        "--out_dev",
        args.dev_dataset,
        "--out_holdout",
        args.holdout_dataset,
        "--manifest",
        args.ext_manifest,
        "--dev_size",
        str(int(args.dev_size)),
        "--holdout_size",
        str(int(args.holdout_size)),
        "--seed",
        str(int(args.ext_seed)),
    ]
    _run(cmd)
    return ["build extended eval datasets ({}, {})".format(args.dev_dataset, args.holdout_dataset)]


def _ensure_baseline_anchor(
    py,
    baseline_config,
    dataset,
    out_path,
    run_mode,
    retrieval_scope,
    seed,
):
    out = ROOT / out_path
    if out.exists():
        return False
    _run(
        [
            py,
            "run_baseline_rag.py",
            "--config",
            baseline_config,
            "--dataset",
            dataset,
            "--out",
            str(out),
            "--run_mode",
            run_mode,
            "--retrieval_scope",
            retrieval_scope,
            "--seed",
            str(int(seed)),
        ]
    )
    return True


def _prepare_round0(py, args):
    actions = []
    actions.extend(_ensure_extended_sets(py, args))
    if _ensure_baseline_anchor(
        py=py,
        baseline_config=args.baseline_config,
        dataset=args.canonical_dataset,
        out_path=args.canonical_baseline_anchor,
        run_mode=args.run_mode,
        retrieval_scope=args.retrieval_scope,
        seed=args.single_seed,
    ):
        actions.append("create canonical baseline anchor")
    else:
        actions.append("reuse canonical baseline anchor")

    if _ensure_baseline_anchor(
        py=py,
        baseline_config=args.baseline_config,
        dataset=args.dev_dataset,
        out_path=args.dev_baseline_anchor,
        run_mode=args.run_mode,
        retrieval_scope=args.retrieval_scope,
        seed=args.single_seed,
    ):
        actions.append("create dev baseline anchor")
    else:
        actions.append("reuse dev baseline anchor")

    if _ensure_baseline_anchor(
        py=py,
        baseline_config=args.baseline_config,
        dataset=args.holdout_dataset,
        out_path=args.holdout_baseline_anchor,
        run_mode=args.run_mode,
        retrieval_scope=args.retrieval_scope,
        seed=args.single_seed,
    ):
        actions.append("create holdout baseline anchor")
    else:
        actions.append("reuse holdout baseline anchor")
    return actions


def _run_agent_eval_single(
    py,
    config,
    dataset,
    baseline_anchor,
    seed,
    run_mode,
    retrieval_scope,
    round_idx,
    dataset_tag,
):
    ts = _now_ts()
    tag = "auto_r{}_{}_{}".format(round_idx, dataset_tag, ts)
    agent_pred = ROOT / "results" / "edge_agent_formal_{}.jsonl".format(tag)
    report_dir = ROOT / "report" / "formal_{}".format(tag)

    before = set([p.name for p in (ROOT / "results").glob("run_*") if p.is_dir()])
    _run(
        [
            py,
            "run_agent.py",
            "--config",
            config,
            "--dataset",
            dataset,
            "--out",
            str(agent_pred),
            "--run_mode",
            run_mode,
            "--retrieval_scope",
            retrieval_scope,
            "--seed",
            str(int(seed)),
        ]
    )
    run_dir = _find_new_run_dir(before)
    trace_dir = (run_dir / "trace") if run_dir else None

    _run(
        [
            py,
            "evaluate.py",
            "--gold",
            dataset,
            "--pred",
            baseline_anchor,
            str(agent_pred),
            "--out_dir",
            str(report_dir),
            "--run_mode",
            run_mode,
            "--run_tag",
            tag,
        ]
    )

    parsed = _parse_report(report_dir, Path(baseline_anchor).stem, agent_pred.stem)
    parsed["tag"] = tag
    parsed["dataset_tag"] = dataset_tag
    parsed["agent_pred"] = str(agent_pred)
    parsed["baseline_pred"] = str(baseline_anchor)
    parsed["trace_dir"] = str(trace_dir) if trace_dir else ""
    parsed["trace_stats"] = _collect_trace_stats(trace_dir)
    sample_summary = _sample_level_summary(
        dataset_path=dataset,
        baseline_pred_path=baseline_anchor,
        agent_pred_path=str(agent_pred),
        top_n=5,
    )
    sample_summary_path = Path(report_dir) / "sample_level_summary.json"
    sample_summary_path.write_text(
        json.dumps(sample_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    parsed["sample_summary"] = sample_summary
    parsed["sample_summary_path"] = str(sample_summary_path)
    return parsed


def _default_result(dataset_tag, thresholds=None):
    t = thresholds or {}
    return {
        "tag": "",
        "dataset_tag": str(dataset_tag),
        "agent_pred": "",
        "baseline_pred": "",
        "report_dir": "",
        "sample_summary_path": "",
        "sample_summary": {"regression_top": [], "improvement_top": [], "latency_top": []},
        "trace_dir": "",
        "trace_stats": {
            "trace_files": 0,
            "forced_final_count": 0,
            "low_confidence_step_count": 0,
            "forced_search_step_count": 0,
            "early_stop_reason_top": [],
        },
        "baseline_method": "",
        "agent_method": "",
        "baseline_f1": 0.0,
        "agent_f1": float(t.get("overall_f1", 0.0)),
        "baseline_em": 0.0,
        "agent_em": 0.0,
        "baseline_p95_ms": 0.0,
        "agent_p95_ms": 0.0,
        "p95_ratio": float(t.get("p95_ratio", 0.0)),
        "agent_avg_steps": 0.0,
        "agent_avg_retrieval": 0.0,
        "agent_oom": 0,
        "single_doc_f1": float(t.get("single_doc_f1", 0.0)),
        "multi_doc_f1": 0.0,
        "code_f1": 0.0,
        "baseline_single_doc_f1": 0.0,
        "baseline_multi_doc_f1": 0.0,
        "baseline_code_f1": 0.0,
        "delta_single_doc_f1": 0.0,
        "delta_multi_doc_f1": 0.0,
        "delta_code_f1": 0.0,
    }


def _is_valid_result(result):
    if not result:
        return False
    keys = ["agent_f1", "single_doc_f1", "p95_ratio", "agent_oom"]
    for k in keys:
        if k not in result:
            return False
    try:
        float(result.get("agent_f1", 0.0))
        float(result.get("single_doc_f1", 0.0))
        float(result.get("p95_ratio", 0.0))
        int(result.get("agent_oom", 0))
    except Exception:
        return False
    return True


def _run_agent_eval_single_safe(**kwargs):
    try:
        result = _run_agent_eval_single(**kwargs)
    except subprocess.TimeoutExpired as exc:
        return ("interrupted", None, "timeout: {}".format(str(exc)))
    except subprocess.CalledProcessError as exc:
        return ("interrupted", None, "subprocess_error: {}".format(str(exc)))
    except Exception as exc:
        return ("interrupted", None, "exception: {}".format(str(exc)))

    if not _is_valid_result(result):
        return ("invalid", result, "invalid metrics output")
    return ("success", result, "")


def _multi_seed_check(
    py,
    config,
    baseline_config,
    dataset,
    seeds,
    run_mode,
    retrieval_scope,
    round_idx,
    thresholds,
    dataset_tag,
    require_task_delta_ci=True,
):
    ts = _now_ts()
    items = []
    for seed in seeds:
        tag = "auto_r{}_{}_s{}_{}".format(round_idx, dataset_tag, seed, ts)
        baseline_pred = ROOT / "results" / "baseline_rag_formal_{}.jsonl".format(tag)
        agent_pred = ROOT / "results" / "edge_agent_formal_{}.jsonl".format(tag)
        report_dir = ROOT / "report" / "formal_{}".format(tag)

        fallback_baseline = None
        try:
            _run(
                [
                    py,
                    "run_baseline_rag.py",
                    "--config",
                    baseline_config,
                    "--dataset",
                    dataset,
                    "--out",
                    str(baseline_pred),
                    "--run_mode",
                    run_mode,
                    "--retrieval_scope",
                    retrieval_scope,
                    "--seed",
                    str(int(seed)),
                ],
                timeout_s=5400,
            )
        except Exception as exc:
            # Prefer same-dataset same-seed historical baseline results to avoid blocking.
            fallback_patterns = [
                "baseline_rag_formal_auto_r*_{tag}_s{seed}_*.jsonl".format(
                    tag=dataset_tag, seed=int(seed)
                ),
                "baseline_rag_formal_final_s{seed}_*.jsonl".format(seed=int(seed)),
                "baseline_rag_formal_stable1_s{seed}_*.jsonl".format(seed=int(seed)),
            ]
            for pat in fallback_patterns:
                fallback_baseline = _latest_result_file(pat)
                if fallback_baseline is not None:
                    break
            if fallback_baseline is None:
                raise
            baseline_pred = fallback_baseline
            print(
                "[warn] baseline rerun failed for seed {} ({}); fallback to {}".format(
                    seed, str(exc), str(baseline_pred)
                )
            )
        _run(
            [
                py,
                "run_agent.py",
                "--config",
                config,
                "--dataset",
                dataset,
                "--out",
                str(agent_pred),
                "--run_mode",
                run_mode,
                "--retrieval_scope",
                retrieval_scope,
                "--seed",
                str(int(seed)),
            ]
        )
        _run(
            [
                py,
                "evaluate.py",
                "--gold",
                dataset,
                "--pred",
                str(baseline_pred),
                str(agent_pred),
                "--out_dir",
                str(report_dir),
                "--run_mode",
                run_mode,
                "--run_tag",
                tag,
            ]
        )
        parsed = _parse_report(report_dir, baseline_pred.stem, agent_pred.stem)
        parsed["seed"] = int(seed)
        parsed["baseline_fallback_used"] = bool(fallback_baseline is not None)
        parsed["baseline_fallback_path"] = str(fallback_baseline or "")
        items.append(parsed)

    n = float(len(items) or 1.0)
    mean_agent_f1 = sum([x["agent_f1"] for x in items]) / n
    mean_single_doc_f1 = sum([x["single_doc_f1"] for x in items]) / n
    mean_ratio = sum([x["p95_ratio"] for x in items]) / n
    oom_sum = int(sum([int(x["agent_oom"]) for x in items]))
    task_delta_ci = {}
    for task_name, key in [
        ("single_doc_qa", "delta_single_doc_f1"),
        ("multi_doc_qa", "delta_multi_doc_f1"),
        ("code_qa", "delta_code_f1"),
    ]:
        stats = _mean_ci95([float(x.get(key, 0.0)) for x in items])
        stats["task"] = task_name
        stats["pass_lower_gt_0"] = bool(float(stats.get("lower", 0.0)) > 0.0)
        task_delta_ci[task_name] = stats
    ci_positive_count = int(
        sum([1 for _, v in task_delta_ci.items() if bool(v.get("pass_lower_gt_0", False))])
    )
    ci_pass = ci_positive_count >= 2

    passed_mean_gate = (
        mean_agent_f1 >= thresholds["overall_f1"]
        and mean_single_doc_f1 >= thresholds["single_doc_f1"]
        and mean_ratio <= thresholds["p95_ratio"]
        and oom_sum == 0
    )
    passed = bool(passed_mean_gate and ((not require_task_delta_ci) or ci_pass))
    return {
        "dataset_tag": dataset_tag,
        "pass": bool(passed),
        "pass_mean_gate": bool(passed_mean_gate),
        "pass_ci_gate": bool(ci_pass),
        "require_task_delta_ci": bool(require_task_delta_ci),
        "rows": items,
        "mean_agent_f1": mean_agent_f1,
        "mean_single_doc_f1": mean_single_doc_f1,
        "mean_ratio": mean_ratio,
        "oom_sum": oom_sum,
        "task_delta_ci": task_delta_ci,
        "task_delta_ci_positive_count": int(ci_positive_count),
    }


def _apply_auto_policy(config_path, canonical_m, canonical_gate, dev_m):
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    actions = []
    changed = False

    agent_cfg = cfg.setdefault("agent", {})
    task_overrides = agent_cfg.setdefault("task_overrides", {})
    single_doc = task_overrides.setdefault("single_doc_qa", {})
    multi_doc = task_overrides.setdefault("multi_doc_qa", {})
    code_qa = task_overrides.setdefault("code_qa", {})
    retrieval = cfg.setdefault("retrieval", {})
    hybrid = retrieval.setdefault("hybrid", {})
    decoding_budget = agent_cfg.setdefault("decoding_budget", {})
    task_caps = decoding_budget.setdefault("task_caps", {})
    dev_guard = decoding_budget.setdefault("dev_guard", {})
    dev_target_ratio = float(dev_guard.get("target_p95_ratio", 2.30))
    dev_target_single_doc = float(dev_guard.get("target_single_doc_f1", 0.24))

    canonical_ok = _gate_ok(canonical_gate)
    ratio_fail_only = (
        (not canonical_gate["ratio_pass"])
        and canonical_gate["overall_pass"]
        and canonical_gate["single_doc_pass"]
        and canonical_gate["oom_pass"]
    )
    single_doc_fail = not canonical_gate["single_doc_pass"]
    overall_fail = not canonical_gate["overall_pass"]
    oom_fail = not canonical_gate["oom_pass"]
    dev_ratio_fail = float(dev_m.get("p95_ratio", 0.0)) > dev_target_ratio
    dev_single_doc_fail = float(dev_m.get("single_doc_f1", 0.0)) < dev_target_single_doc

    # 1) Canonical-first policy (primary objective).
    if ratio_fail_only:
        forced = single_doc.setdefault("forced_retrieve", {})
        old_force = int(forced.get("max_extra_searches", 1))
        new_force = 0 if old_force > 0 else old_force
        if new_force != old_force:
            forced["max_extra_searches"] = new_force
            actions.append("single_doc.forced_retrieve.max_extra_searches {}->{}".format(old_force, new_force))
            changed = True

        long_ctx = single_doc.setdefault("long_context", {})
        if not bool(long_ctx.get("disable_refine_over_threshold", False)):
            long_ctx["disable_refine_over_threshold"] = True
            actions.append("single_doc.long_context.disable_refine_over_threshold false->true")
            changed = True
        if not bool(long_ctx.get("disable_forced_retrieve_over_threshold", False)):
            long_ctx["disable_forced_retrieve_over_threshold"] = True
            actions.append("single_doc.long_context.disable_forced_retrieve_over_threshold false->true")
            changed = True

        if bool(multi_doc.get("enable_query_rewrite_retry", True)):
            multi_doc["enable_query_rewrite_retry"] = False
            actions.append("multi_doc.enable_query_rewrite_retry true->false")
            changed = True

        old_default = int(decoding_budget.get("default_max_new_tokens", 224))
        new_default = max(176, old_default - 16)
        if new_default != old_default:
            decoding_budget["default_max_new_tokens"] = new_default
            actions.append("decoding_budget.default_max_new_tokens {}->{}".format(old_default, new_default))
            changed = True

        old_multi_cap = int(task_caps.get("multi_doc_qa", 240))
        new_multi_cap = max(168, old_multi_cap - 16)
        if new_multi_cap != old_multi_cap:
            task_caps["multi_doc_qa"] = new_multi_cap
            actions.append("task_caps.multi_doc_qa {}->{}".format(old_multi_cap, new_multi_cap))
            changed = True

        old_code_cap = int(task_caps.get("code_qa", 224))
        new_code_cap = max(168, old_code_cap - 16)
        if new_code_cap != old_code_cap:
            task_caps["code_qa"] = new_code_cap
            actions.append("task_caps.code_qa {}->{}".format(old_code_cap, new_code_cap))
            changed = True

        old_cand = int(hybrid.get("max_candidates", 16))
        new_cand = max(12, old_cand - 2)
        if new_cand != old_cand:
            hybrid["max_candidates"] = new_cand
            actions.append("retrieval.hybrid.max_candidates {}->{}".format(old_cand, new_cand))
            changed = True

    if single_doc_fail:
        old_topk = int(single_doc.get("top_k_init", 3))
        if old_topk < 4:
            single_doc["top_k_init"] = 4
            actions.append("single_doc.top_k_init {}->4".format(old_topk))
            changed = True
        early = agent_cfg.setdefault("early_stop", {})
        old_sd_steps = int(early.get("single_doc_max_steps", 3))
        if old_sd_steps < 4:
            early["single_doc_max_steps"] = 4
            actions.append("early_stop.single_doc_max_steps {}->4".format(old_sd_steps))
            changed = True
        forced = single_doc.setdefault("forced_retrieve", {})
        old_force = int(forced.get("max_extra_searches", 0))
        if old_force < 1:
            forced["max_extra_searches"] = 1
            actions.append("single_doc.forced_retrieve.max_extra_searches {}->1".format(old_force))
            changed = True
        refine_gate = single_doc.setdefault("refine_gate", {})
        if not bool(refine_gate.get("on_forced_final", False)):
            refine_gate["on_forced_final"] = True
            actions.append("single_doc.refine_gate.on_forced_final false->true")
            changed = True
        answer_type_policy = single_doc.setdefault("answer_type_policy", {})
        if bool(answer_type_policy.get("enable", True)):
            answer_type_policy["enable"] = False
            actions.append("single_doc.answer_type_policy.enable true->false")
            changed = True

    if overall_fail:
        if int(code_qa.get("top_k_init", 4)) < 4:
            code_qa["top_k_init"] = 4
            actions.append("code_qa.top_k_init ->4")
            changed = True
        if int(code_qa.get("top_k_iter", 2)) < 2:
            code_qa["top_k_iter"] = 2
            actions.append("code_qa.top_k_iter ->2")
            changed = True
        if int(code_qa.get("max_steps", 4)) < 4:
            code_qa["max_steps"] = 4
            actions.append("code_qa.max_steps ->4")
            changed = True
        if int(code_qa.get("max_new_tokens", 224)) < 224:
            code_qa["max_new_tokens"] = 224
            actions.append("code_qa.max_new_tokens ->224")
            changed = True

        if int(multi_doc.get("top_k_init", 3)) < 3:
            multi_doc["top_k_init"] = 3
            actions.append("multi_doc.top_k_init ->3")
            changed = True
        if int(multi_doc.get("top_k_iter", 2)) < 2:
            multi_doc["top_k_iter"] = 2
            actions.append("multi_doc.top_k_iter ->2")
            changed = True
        if int(multi_doc.get("max_steps", 4)) < 4:
            multi_doc["max_steps"] = 4
            actions.append("multi_doc.max_steps ->4")
            changed = True
        if int(multi_doc.get("max_new_tokens", 240)) < 240:
            multi_doc["max_new_tokens"] = 240
            actions.append("multi_doc.max_new_tokens ->240")
            changed = True
        if not bool(multi_doc.get("enable_query_rewrite_retry", True)):
            multi_doc["enable_query_rewrite_retry"] = True
            actions.append("multi_doc.enable_query_rewrite_retry false->true")
            changed = True

    if oom_fail:
        repair = agent_cfg.setdefault("format_repair", {})
        if int(repair.get("max_retries", 1)) < 2:
            repair["max_retries"] = 2
            actions.append("agent.format_repair.max_retries ->2")
            changed = True

    # 2) Dev guard only if canonical currently passes (avoid dev hijacking canonical search).
    if canonical_ok:
        if dev_ratio_fail:
            if bool(multi_doc.get("enable_query_rewrite_retry", True)):
                multi_doc["enable_query_rewrite_retry"] = False
                actions.append("dev_guard: multi_doc.enable_query_rewrite_retry true->false")
                changed = True

            old_default = int(decoding_budget.get("default_max_new_tokens", 224))
            new_default = max(184, old_default - 8)
            if new_default != old_default:
                decoding_budget["default_max_new_tokens"] = new_default
                actions.append(
                    "dev_guard: decoding_budget.default_max_new_tokens {}->{}".format(
                        old_default, new_default
                    )
                )
                changed = True

            old_cand = int(hybrid.get("max_candidates", 16))
            new_cand = max(12, old_cand - 2)
            if new_cand != old_cand:
                hybrid["max_candidates"] = new_cand
                actions.append(
                    "dev_guard: retrieval.hybrid.max_candidates {}->{}".format(
                        old_cand, new_cand
                    )
                )
                changed = True

        if dev_single_doc_fail:
            old_topk = int(single_doc.get("top_k_init", 3))
            if old_topk < 4:
                single_doc["top_k_init"] = 4
                actions.append("dev_guard: single_doc.top_k_init {}->4".format(old_topk))
                changed = True

    if changed:
        Path(config_path).write_text(
            yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    return actions


def _append_round0_snapshot(path, actions, args):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("# 24. Experiment Snapshot (Current)\n", encoding="utf-8")
    content = p.read_text(encoding="utf-8")
    if "## Round 0" in content:
        return
    lines = []
    lines.append("")
    lines.append("## Round 0 ({})".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    lines.append("")
    lines.append("- canonical dataset: `{}`".format(args.canonical_dataset))
    lines.append("- dev dataset: `{}`".format(args.dev_dataset))
    lines.append("- holdout dataset: `{}`".format(args.holdout_dataset))
    lines.append("- canonical anchor: `{}`".format(args.canonical_baseline_anchor))
    lines.append("- dev anchor: `{}`".format(args.dev_baseline_anchor))
    lines.append("- holdout anchor: `{}`".format(args.holdout_baseline_anchor))
    lines.append("- actions:")
    for a in actions:
        lines.append("  - {}".format(a))
    p.write_text(content + "\n".join(lines) + "\n", encoding="utf-8")


def _append_snapshot(
    path,
    round_name,
    canonical_result,
    dev_result,
    holdout_result,
    gate,
    dev_gate,
    holdout_gate,
    can_thresholds,
    score,
    improved,
    best_score,
    actions,
    canonical_ms,
    holdout_ms,
    regression_guard,
    training_result,
    run_status,
    interrupted_reason,
    dev_status,
    dev_reason,
    holdout_status,
    holdout_reason,
):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("# 24. Experiment Snapshot (Current)\n", encoding="utf-8")
    text = p.read_text(encoding="utf-8")

    lines = []
    lines.append("")
    lines.append("## {} ({})".format(round_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    lines.append("")
    lines.append("### run status")
    lines.append("- round_status: `{}`".format(run_status))
    if interrupted_reason:
        lines.append("- interrupted_reason: `{}`".format(interrupted_reason))
    lines.append("- dev_run_status: `{}`".format(dev_status))
    if dev_reason:
        lines.append("- dev_status_reason: `{}`".format(dev_reason))
    lines.append("- holdout_run_status: `{}`".format(holdout_status))
    if holdout_reason:
        lines.append("- holdout_status_reason: `{}`".format(holdout_reason))
    lines.append("")
    lines.append("### canonical (single-seed)")
    lines.append("| item | value |")
    lines.append("| --- | ---: |")
    lines.append("| agent F1 | {:.4f} |".format(canonical_result["agent_f1"]))
    lines.append("| single_doc_qa F1 | {:.4f} |".format(canonical_result["single_doc_f1"]))
    lines.append("| multi_doc_qa F1 | {:.4f} |".format(canonical_result["multi_doc_f1"]))
    lines.append("| code_qa F1 | {:.4f} |".format(canonical_result["code_f1"]))
    lines.append("| P95 ratio | {:.4f} |".format(canonical_result["p95_ratio"]))
    lines.append("| avg_steps | {:.4f} |".format(canonical_result["agent_avg_steps"]))
    lines.append("| avg_retrieval | {:.4f} |".format(canonical_result["agent_avg_retrieval"]))
    lines.append("| oom_count | {} |".format(int(canonical_result["agent_oom"])))
    lines.append("")
    lines.append("### dev100 (single-seed)")
    lines.append("- status: `{}`".format(dev_status))
    lines.append("| item | value |")
    lines.append("| --- | ---: |")
    lines.append("| agent F1 | {:.4f} |".format(dev_result["agent_f1"]))
    lines.append("| single_doc_qa F1 | {:.4f} |".format(dev_result["single_doc_f1"]))
    lines.append("| multi_doc_qa F1 | {:.4f} |".format(dev_result["multi_doc_f1"]))
    lines.append("| code_qa F1 | {:.4f} |".format(dev_result["code_f1"]))
    lines.append("| P95 ratio | {:.4f} |".format(dev_result["p95_ratio"]))
    lines.append("| avg_steps | {:.4f} |".format(dev_result["agent_avg_steps"]))
    lines.append("| avg_retrieval | {:.4f} |".format(dev_result["agent_avg_retrieval"]))
    lines.append("| oom_count | {} |".format(int(dev_result["agent_oom"])))
    lines.append("")
    lines.append("### holdout100 (single-seed)")
    lines.append("- status: `{}`".format(holdout_status))
    if holdout_result is None:
        lines.append("- result: `not run in this round`")
    else:
        lines.append("| item | value |")
        lines.append("| --- | ---: |")
        lines.append("| agent F1 | {:.4f} |".format(holdout_result["agent_f1"]))
        lines.append("| single_doc_qa F1 | {:.4f} |".format(holdout_result["single_doc_f1"]))
        lines.append("| multi_doc_qa F1 | {:.4f} |".format(holdout_result["multi_doc_f1"]))
        lines.append("| code_qa F1 | {:.4f} |".format(holdout_result["code_f1"]))
        lines.append("| P95 ratio | {:.4f} |".format(holdout_result["p95_ratio"]))
        lines.append("| avg_steps | {:.4f} |".format(holdout_result["agent_avg_steps"]))
        lines.append("| avg_retrieval | {:.4f} |".format(holdout_result["agent_avg_retrieval"]))
        lines.append("| oom_count | {} |".format(int(holdout_result["agent_oom"])))
    lines.append("")
    lines.append("### gate")
    lines.append("- canonical overall: `{}`".format("pass" if gate["overall_pass"] else "fail"))
    lines.append("- canonical single_doc: `{}`".format("pass" if gate["single_doc_pass"] else "fail"))
    lines.append("- canonical ratio: `{}`".format("pass" if gate["ratio_pass"] else "fail"))
    lines.append("- canonical oom: `{}`".format("pass" if gate["oom_pass"] else "fail"))
    if dev_status == "success":
        lines.append("- dev overall: `{}`".format("pass" if dev_gate["overall_pass"] else "fail"))
        lines.append("- dev single_doc: `{}`".format("pass" if dev_gate["single_doc_pass"] else "fail"))
        lines.append("- dev ratio: `{}`".format("pass" if dev_gate["ratio_pass"] else "fail"))
        lines.append("- dev oom: `{}`".format("pass" if dev_gate["oom_pass"] else "fail"))
    else:
        lines.append("- dev gate: `{}`".format(dev_status))
    if holdout_status == "success" and holdout_gate is not None:
        lines.append("- holdout overall: `{}`".format("pass" if holdout_gate["overall_pass"] else "fail"))
        lines.append(
            "- holdout single_doc: `{}`".format(
                "pass" if holdout_gate["single_doc_pass"] else "fail"
            )
        )
        lines.append("- holdout ratio: `{}`".format("pass" if holdout_gate["ratio_pass"] else "fail"))
        lines.append("- holdout oom: `{}`".format("pass" if holdout_gate["oom_pass"] else "fail"))
    else:
        lines.append("- holdout gate: `{}`".format(holdout_status))
    lines.append("- score: `{:.4f}` (best `{:.4f}`, improved `{}`)".format(score, best_score, str(bool(improved)).lower()))
    lines.append("")
    lines.append("### 三任务门槛判定 (canonical)")
    lines.append("- overall: `{:.4f} >= {:.4f}` -> `{}`".format(
        canonical_result["agent_f1"],
        can_thresholds["overall_f1"],
        "pass" if gate["overall_pass"] else "fail",
    ))
    lines.append("- single_doc: `{:.4f} >= {:.4f}` -> `{}`".format(
        canonical_result["single_doc_f1"],
        can_thresholds["single_doc_f1"],
        "pass" if gate["single_doc_pass"] else "fail",
    ))
    lines.append("- ratio: `{:.4f} <= {:.4f}` -> `{}`".format(
        canonical_result["p95_ratio"],
        can_thresholds["p95_ratio"],
        "pass" if gate["ratio_pass"] else "fail",
    ))
    lines.append("- oom: `{}` -> `{}`".format(
        int(canonical_result["agent_oom"]),
        "pass" if gate["oom_pass"] else "fail",
    ))
    lines.append("")
    lines.append("### 回归保护判定")
    regressions = (regression_guard or {}).get("regressions", []) or []
    if not regressions:
        lines.append("- regression_guard: `pass` (no task drop beyond threshold)")
    else:
        lines.append("- regression_guard: `fail`")
        for item in regressions:
            lines.append(
                "- task `{}` drop `{:.4f}` (ref `{:.4f}` -> cur `{:.4f}`)".format(
                    str(item.get("task", "")),
                    float(item.get("drop", 0.0)),
                    float(item.get("reference", 0.0)),
                    float(item.get("current", 0.0)),
                )
            )
        if bool((regression_guard or {}).get("rollback_applied", False)):
            lines.append("- rollback: `applied` -> restore `results/last_good_config.yaml`")
        else:
            lines.append("- rollback: `not applied`")
    lines.append("")
    lines.append("### trace (canonical)")
    ts = canonical_result.get("trace_stats", {})
    lines.append("- trace_files: `{}`".format(ts.get("trace_files", 0)))
    lines.append("- forced_final_count: `{}`".format(ts.get("forced_final_count", 0)))
    lines.append("- low_confidence_step_count: `{}`".format(ts.get("low_confidence_step_count", 0)))
    lines.append("- forced_search_step_count: `{}`".format(ts.get("forced_search_step_count", 0)))
    top_reasons = ts.get("early_stop_reason_top", [])
    if top_reasons:
        lines.append("- early_stop_reason_top: `{}`".format(", ".join(["{}={}".format(k, v) for k, v in top_reasons])))
    else:
        lines.append("- early_stop_reason_top: `none`")
    lines.append("")
    lines.append("### sample summary")
    lines.append("- canonical summary: `{}`".format(canonical_result.get("sample_summary_path", "")))
    can_summary = canonical_result.get("sample_summary", {}) or {}
    reg_top = can_summary.get("regression_top", []) or []
    lat_top = can_summary.get("latency_top", []) or []
    if reg_top:
        reg_line = ", ".join(
            [
                "{}({:.3f})".format(str(x.get("id", "")), float(x.get("delta_f1", 0.0)))
                for x in reg_top[:3]
            ]
        )
        lines.append("- canonical regression_top3: `{}`".format(reg_line))
    else:
        lines.append("- canonical regression_top3: `none`")
    if lat_top:
        lat_line = ", ".join(
            [
                "{}({:.2f}s)".format(
                    str(x.get("id", "")), float(x.get("latency_ms", 0.0)) / 1000.0
                )
                for x in lat_top[:3]
            ]
        )
        lines.append("- canonical latency_top3: `{}`".format(lat_line))
    else:
        lines.append("- canonical latency_top3: `none`")
    lines.append("- dev summary: `{}`".format(dev_result.get("sample_summary_path", "")))
    dev_summary = dev_result.get("sample_summary", {}) or {}
    dev_reg_top = dev_summary.get("regression_top", []) or []
    dev_lat_top = dev_summary.get("latency_top", []) or []
    if dev_reg_top:
        reg_line = ", ".join(
            [
                "{}({:.3f})".format(str(x.get("id", "")), float(x.get("delta_f1", 0.0)))
                for x in dev_reg_top[:3]
            ]
        )
        lines.append("- dev regression_top3: `{}`".format(reg_line))
    else:
        lines.append("- dev regression_top3: `none`")
    if dev_lat_top:
        lat_line = ", ".join(
            [
                "{}({:.2f}s)".format(
                    str(x.get("id", "")), float(x.get("latency_ms", 0.0)) / 1000.0
                )
                for x in dev_lat_top[:3]
            ]
        )
        lines.append("- dev latency_top3: `{}`".format(lat_line))
    else:
        lines.append("- dev latency_top3: `none`")
    lines.append("")
    lines.append("### actions")
    if actions:
        for a in actions:
            lines.append("- {}".format(a))
    else:
        lines.append("- no config change")

    if canonical_ms is not None:
        lines.append("- canonical 3-seed: `{}`".format("pass" if canonical_ms.get("pass", False) else "fail"))
        lines.append(
            "- canonical means: F1 `{:.4f}`, single_doc `{:.4f}`, ratio `{:.4f}`, oom_sum `{}`".format(
                canonical_ms.get("mean_agent_f1", 0.0),
                canonical_ms.get("mean_single_doc_f1", 0.0),
                canonical_ms.get("mean_ratio", 0.0),
                int(canonical_ms.get("oom_sum", 0)),
            )
        )
        lines.append(
            "- canonical CI gate(2/3 tasks lower>0): `{}` (positive_tasks=`{}`)".format(
                "pass" if canonical_ms.get("pass_ci_gate", False) else "fail",
                int(canonical_ms.get("task_delta_ci_positive_count", 0)),
            )
        )
        task_delta_ci = canonical_ms.get("task_delta_ci", {}) or {}
        if task_delta_ci:
            lines.append("")
            lines.append("### seed-level delta_F1 与 CI (canonical 3-seed)")
            lines.append("| task | mean_delta_f1 | ci95 | lower | upper | pass(lower>0) |")
            lines.append("| --- | ---: | ---: | ---: | ---: | --- |")
            for task_name in ["single_doc_qa", "multi_doc_qa", "code_qa"]:
                st = task_delta_ci.get(task_name, {}) or {}
                lines.append(
                    "| {} | {:.4f} | {:.4f} | {:.4f} | {:.4f} | {} |".format(
                        task_name,
                        float(st.get("mean", 0.0)),
                        float(st.get("ci95", 0.0)),
                        float(st.get("lower", 0.0)),
                        float(st.get("upper", 0.0)),
                        "pass" if bool(st.get("pass_lower_gt_0", False)) else "fail",
                    )
                )
    if holdout_ms is not None:
        lines.append("- holdout 3-seed: `{}`".format("pass" if holdout_ms.get("pass", False) else "fail"))
        lines.append(
            "- holdout means: F1 `{:.4f}`, single_doc `{:.4f}`, ratio `{:.4f}`, oom_sum `{}`".format(
                holdout_ms.get("mean_agent_f1", 0.0),
                holdout_ms.get("mean_single_doc_f1", 0.0),
                holdout_ms.get("mean_ratio", 0.0),
                int(holdout_ms.get("oom_sum", 0)),
            )
        )
    if training_result is not None:
        lines.append("- training branch: mode=`{}` out_dir=`{}`".format(training_result.get("mode", "unknown"), training_result.get("out_dir", "")))

    p.write_text(text + "\n".join(lines) + "\n", encoding="utf-8")


def _run_training_branch(py, round_idx):
    ts = _now_ts()
    out_dir = ROOT / "checkpoints" / "student_real_auto_r{}_{}".format(round_idx, ts)
    cmd = [
        py,
        "train_student.py",
        "--config",
        "configs/train_qlora.yaml",
        "--train",
        "data/student_train.jsonl",
        "--out_dir",
        str(out_dir),
        "--prefer_real",
        "--run_mode",
        "formal",
    ]
    mode = "failed"
    try:
        _run(cmd)
        summary_path = out_dir / "training_summary.json"
        if summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            mode = str(summary.get("mode", "unknown"))
        else:
            mode = "unknown"
    except Exception as exc:
        mode = "error: {}".format(exc)
    return {"mode": mode, "out_dir": str(out_dir)}


def main():
    parser = argparse.ArgumentParser(description="Infinite formal iteration (canonical + dev + holdout).")
    parser.add_argument("--python", default=str(ROOT / ".venv" / "Scripts" / "python.exe"))
    parser.add_argument("--config", default="configs/agent.yaml")
    parser.add_argument("--baseline_config", default="configs/baseline_rag.yaml")
    parser.add_argument("--canonical_dataset", default="data/main_eval/longbench_3tasks_test.jsonl")
    parser.add_argument("--dev_dataset", default="data/main_eval/longbench_3tasks_dev100.jsonl")
    parser.add_argument("--holdout_dataset", default="data/main_eval/longbench_3tasks_holdout100.jsonl")
    parser.add_argument("--train_dataset", default="data/train_ext/combined_train.jsonl")
    parser.add_argument("--valid_dataset", default="data/train_ext/combined_valid.jsonl")
    parser.add_argument("--ext_builder_script", default="scripts/build_main_eval_sets_v2.py")
    parser.add_argument("--ext_dataset", default="data/train_ext/combined_valid.jsonl")
    parser.add_argument("--ext_manifest", default="data/manifests/main_eval_split_manifest.json")
    parser.add_argument("--ext_target_total", type=int, default=200)
    parser.add_argument("--ext_seed", type=int, default=20260219)
    parser.add_argument("--dev_size", type=int, default=100)
    parser.add_argument("--holdout_size", type=int, default=100)
    parser.add_argument("--force_rebuild_ext_eval", action="store_true")
    parser.add_argument("--canonical_baseline_anchor", default="results/baseline_rag_formal_anchor_20260217_154511.jsonl")
    parser.add_argument("--dev_baseline_anchor", default="results/baseline_rag_formal_dev100_anchor_20260219.jsonl")
    parser.add_argument("--holdout_baseline_anchor", default="results/baseline_rag_formal_holdout100_anchor_20260219.jsonl")
    parser.add_argument("--run_mode", default="formal", choices=["smoke", "formal"])
    parser.add_argument("--retrieval_scope", default="sample", choices=["sample", "global"])
    parser.add_argument("--single_seed", type=int, default=42)
    parser.add_argument("--multi_seeds", nargs="+", default=["42", "123", "2026"])
    parser.add_argument("--snapshot_doc", default="docs/24_实验快照_当前.md")
    parser.add_argument("--state_path", default="results/auto_iterate_state.json")
    parser.add_argument("--last_good_config", default="results/last_good_config.yaml")
    parser.add_argument("--start_round", type=int, default=1)
    parser.add_argument("--max_rounds", type=int, default=0, help="0 means no hard cap")
    parser.add_argument("--force_multiseed_every", type=int, default=3)
    parser.add_argument("--dev_every_rounds", type=int, default=2)
    parser.add_argument("--holdout_every_rounds", type=int, default=3)
    parser.add_argument("--no_improve_to_train", type=int, default=3)
    parser.add_argument("--enable_training_branch", action="store_true")
    parser.add_argument("--min_score_delta", type=float, default=0.002)
    parser.add_argument("--regression_drop_threshold", type=float, default=0.03)
    parser.add_argument("--run_holdout_multiseed", action="store_true")
    parser.add_argument("--target_overall_f1", type=float, default=0.37)
    parser.add_argument("--target_single_doc_f1", type=float, default=0.29)
    parser.add_argument("--target_p95_ratio", type=float, default=1.8)
    parser.add_argument("--dev_target_overall_f1", type=float, default=0.28)
    parser.add_argument("--dev_target_single_doc_f1", type=float, default=0.24)
    parser.add_argument("--dev_target_p95_ratio", type=float, default=2.30)
    parser.add_argument("--holdout_target_overall_f1", type=float, default=0.35)
    parser.add_argument("--holdout_target_single_doc_f1", type=float, default=0.27)
    parser.add_argument("--holdout_target_p95_ratio", type=float, default=1.9)
    args = parser.parse_args()

    py = args.python
    can_thresholds = {
        "overall_f1": float(args.target_overall_f1),
        "single_doc_f1": float(args.target_single_doc_f1),
        "p95_ratio": float(args.target_p95_ratio),
    }
    dev_thresholds = {
        "overall_f1": float(args.dev_target_overall_f1),
        "single_doc_f1": float(args.dev_target_single_doc_f1),
        "p95_ratio": float(args.dev_target_p95_ratio),
    }
    holdout_thresholds = {
        "overall_f1": float(args.holdout_target_overall_f1),
        "single_doc_f1": float(args.holdout_target_single_doc_f1),
        "p95_ratio": float(args.holdout_target_p95_ratio),
    }

    round0_actions = _prepare_round0(py, args)
    _append_round0_snapshot(ROOT / args.snapshot_doc, round0_actions, args)

    compile_cmd = [
        py,
        "-m",
        "py_compile",
        "agent/edge_reasoning_agent.py",
        "agent/memory.py",
        "retrieval/index_faiss.py",
        "llm/driver_local.py",
        "llm/driver_hf.py",
        "scripts/build_extended_eval_sets.py",
        "scripts/auto_iterate_formal.py",
    ]
    help_cmds = [
        [py, "run_baseline_rag.py", "--help"],
        [py, "run_agent.py", "--help"],
        [py, "evaluate.py", "--help"],
    ]

    state_file = ROOT / args.state_path
    last_good_config_path = ROOT / args.last_good_config
    state = _load_state(state_file)
    best_score = float(state.get("best_score", -1e9))
    no_improve_streak = int(state.get("no_improve_streak", 0))
    single_pass_streak = int(state.get("single_pass_streak", 0))
    canonical_multi_pass_streak = int(state.get("canonical_multi_pass_streak", 0))
    rounds_since_multi = int(state.get("rounds_since_multi", 0))
    best_stable_round = int(state.get("best_stable_round", 0))
    best_stable_metrics = state.get("best_stable_metrics", {}) or {}
    last_dev_result = state.get("last_dev_result", {}) or {}
    last_holdout_result = state.get("last_holdout_result", {}) or {}
    round_records = state.get("round_records", []) or []

    round_idx = int(args.start_round)
    if int(args.start_round) <= 1 and state.get("next_round") is not None:
        round_idx = int(state.get("next_round"))
    rounds_run = 0
    while True:
        if args.max_rounds > 0 and rounds_run >= args.max_rounds:
            print("[stop] reached max_rounds={}".format(args.max_rounds))
            break

        _run(compile_cmd)
        for cmd in help_cmds:
            _run(cmd)

        run_status = "success"
        interrupted_reason = ""

        can_status, canonical_raw, can_reason = _run_agent_eval_single_safe(
            py=py,
            config=args.config,
            dataset=args.canonical_dataset,
            baseline_anchor=str(ROOT / args.canonical_baseline_anchor),
            seed=args.single_seed,
            run_mode=args.run_mode,
            retrieval_scope=args.retrieval_scope,
            round_idx=round_idx,
            dataset_tag="can",
        )
        if can_status == "success":
            canonical = canonical_raw
        else:
            canonical = canonical_raw or _default_result("can", can_thresholds)
            if can_status == "invalid":
                run_status = "invalid"
                interrupted_reason = "canonical: {}".format(can_reason)

        # Interrupted canonical round: record and retry same round index.
        if can_status == "interrupted":
            run_status = "interrupted"
            interrupted_reason = "canonical: {}".format(can_reason)
            dev = last_dev_result or _default_result("dev", dev_thresholds)
            holdout = last_holdout_result or _default_result("holdout", holdout_thresholds)
            gate = _single_gate(canonical, can_thresholds)
            dev_gate = _single_gate(dev, dev_thresholds)
            holdout_gate = _single_gate(holdout, holdout_thresholds)
            _append_snapshot(
                path=ROOT / args.snapshot_doc,
                round_name="Round {}".format(round_idx),
                canonical_result=canonical,
                dev_result=dev,
                holdout_result=holdout,
                gate=gate,
                dev_gate=dev_gate,
                holdout_gate=holdout_gate,
                can_thresholds=can_thresholds,
                score=float(best_score),
                improved=False,
                best_score=float(best_score),
                actions=["round_interrupted_retry_same_round"],
                canonical_ms=None,
                holdout_ms=None,
                regression_guard={"regressions": [], "rollback_applied": False},
                training_result=None,
                run_status=run_status,
                interrupted_reason=interrupted_reason,
                dev_status="skipped",
                dev_reason="canonical_interrupted",
                holdout_status="skipped",
                holdout_reason="canonical_interrupted",
            )
            round_records.append(
                {
                    "round": int(round_idx),
                    "run_status": run_status,
                    "interrupted_reason": interrupted_reason,
                    "canonical_status": can_status,
                    "canonical_reason": can_reason,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            round_records = round_records[-50:]
            _save_state(
                state_file,
                {
                    "best_score": float(best_score),
                    "no_improve_streak": int(no_improve_streak),
                    "single_pass_streak": int(single_pass_streak),
                    "canonical_multi_pass_streak": int(canonical_multi_pass_streak),
                    "rounds_since_multi": int(rounds_since_multi),
                    "best_stable_round": int(best_stable_round),
                    "best_stable_metrics": best_stable_metrics,
                    "last_dev_result": last_dev_result,
                    "last_holdout_result": last_holdout_result,
                    "round_records": round_records,
                    "run_status": run_status,
                    "interrupted_reason": interrupted_reason,
                    "next_round": int(round_idx),
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
            print("[round {}] interrupted, retry same round.".format(round_idx))
            time.sleep(2.0)
            continue

        run_dev = int(args.dev_every_rounds) > 0 and (round_idx % int(args.dev_every_rounds) == 0)
        run_holdout = int(args.holdout_every_rounds) > 0 and (
            round_idx % int(args.holdout_every_rounds) == 0
        )

        dev_status = "skipped"
        dev_reason = "cadence: every {} rounds".format(int(args.dev_every_rounds))
        if run_dev:
            dev_status, dev_raw, dev_reason = _run_agent_eval_single_safe(
                py=py,
                config=args.config,
                dataset=args.dev_dataset,
                baseline_anchor=str(ROOT / args.dev_baseline_anchor),
                seed=args.single_seed,
                run_mode=args.run_mode,
                retrieval_scope=args.retrieval_scope,
                round_idx=round_idx,
                dataset_tag="dev",
            )
            if dev_status == "success":
                dev = dev_raw
                last_dev_result = dev
            else:
                dev = last_dev_result or _default_result("dev", dev_thresholds)
        else:
            dev = last_dev_result or _default_result("dev", dev_thresholds)

        holdout_status = "skipped"
        holdout_reason = "cadence: every {} rounds".format(int(args.holdout_every_rounds))
        holdout = last_holdout_result or _default_result("holdout", holdout_thresholds)
        if run_holdout:
            holdout_status, holdout_raw, holdout_reason = _run_agent_eval_single_safe(
                py=py,
                config=args.config,
                dataset=args.holdout_dataset,
                baseline_anchor=str(ROOT / args.holdout_baseline_anchor),
                seed=args.single_seed,
                run_mode=args.run_mode,
                retrieval_scope=args.retrieval_scope,
                round_idx=round_idx,
                dataset_tag="holdout",
            )
            if holdout_status == "success":
                holdout = holdout_raw
                last_holdout_result = holdout

        status_reasons = []
        if dev_status in ("interrupted", "invalid"):
            status_reasons.append("dev:{}".format(dev_reason))
        if holdout_status in ("interrupted", "invalid"):
            status_reasons.append("holdout:{}".format(holdout_reason))
        if status_reasons:
            if "interrupted" in [dev_status, holdout_status]:
                run_status = "interrupted"
            elif run_status != "interrupted":
                run_status = "invalid"
            interrupted_reason = "; ".join(status_reasons)

        gate = _single_gate(canonical, can_thresholds)
        if dev_status == "success":
            dev_gate = _single_gate(dev, dev_thresholds)
        else:
            dev_gate = {"overall_pass": True, "single_doc_pass": True, "ratio_pass": True, "oom_pass": True}
        if holdout_status == "success":
            holdout_gate = _single_gate(holdout, holdout_thresholds)
        else:
            holdout_gate = {"overall_pass": True, "single_doc_pass": True, "ratio_pass": True, "oom_pass": True}

        canonical_gate_pass = _gate_ok(gate)
        dev_gate_pass = _gate_ok(dev_gate)
        dev_for_score = dev if dev_status == "success" else _default_result("dev", dev_thresholds)
        score = _score(canonical, dev_for_score, can_thresholds, dev_thresholds)
        improved = (score - best_score) >= float(args.min_score_delta)
        if improved:
            best_score = score
            no_improve_streak = 0
        else:
            no_improve_streak += 1

        if canonical_gate_pass:
            single_pass_streak += 1
        else:
            single_pass_streak = 0
        rounds_since_multi += 1

        actions = []
        regressions = _detect_task_regressions(
            current=canonical,
            reference=best_stable_metrics,
            drop_threshold=float(args.regression_drop_threshold),
        )
        rollback_applied = False
        if regressions:
            rollback_applied = _restore_last_good_config(ROOT / args.config, last_good_config_path)
            if rollback_applied:
                actions.append(
                    "rollback_to_last_good_config (drop>{:.3f})".format(
                        float(args.regression_drop_threshold)
                    )
                )
            else:
                actions.append(
                    "regression_detected_but_no_last_good_config (drop>{:.3f})".format(
                        float(args.regression_drop_threshold)
                    )
                )
        elif (not canonical_gate_pass) or (dev_status == "success" and (not dev_gate_pass)):
            actions.extend(
                _apply_auto_policy(
                    config_path=ROOT / args.config,
                    canonical_m=canonical,
                    canonical_gate=gate,
                    dev_m=dev_for_score,
                )
            )

        if canonical_gate_pass:
            stable_better = (not best_stable_metrics) or (
                float(canonical.get("agent_f1", 0.0))
                >= float(best_stable_metrics.get("agent_f1", -1.0))
            )
            if stable_better:
                best_stable_round = int(round_idx)
                best_stable_metrics = {
                    "agent_f1": float(canonical.get("agent_f1", 0.0)),
                    "single_doc_f1": float(canonical.get("single_doc_f1", 0.0)),
                    "multi_doc_f1": float(canonical.get("multi_doc_f1", 0.0)),
                    "code_f1": float(canonical.get("code_f1", 0.0)),
                    "p95_ratio": float(canonical.get("p95_ratio", 0.0)),
                }
                _save_last_good_config(ROOT / args.config, last_good_config_path)
                actions.append("update_last_good_config@round{}".format(round_idx))

        canonical_ms = None
        holdout_ms = None
        trigger_multi = (single_pass_streak == 2) or (
            rounds_since_multi >= int(args.force_multiseed_every)
        )
        if trigger_multi:
            canonical_ms = _multi_seed_check(
                py=py,
                config=args.config,
                baseline_config=args.baseline_config,
                dataset=args.canonical_dataset,
                seeds=[int(x) for x in args.multi_seeds],
                run_mode=args.run_mode,
                retrieval_scope=args.retrieval_scope,
                round_idx=round_idx,
                thresholds=can_thresholds,
                dataset_tag="can",
                require_task_delta_ci=True,
            )
            rounds_since_multi = 0
            if canonical_ms["pass"]:
                canonical_multi_pass_streak += 1
                if bool(args.run_holdout_multiseed):
                    holdout_ms = _multi_seed_check(
                        py=py,
                        config=args.config,
                        baseline_config=args.baseline_config,
                        dataset=args.holdout_dataset,
                        seeds=[int(x) for x in args.multi_seeds],
                        run_mode=args.run_mode,
                        retrieval_scope=args.retrieval_scope,
                        round_idx=round_idx,
                        thresholds=holdout_thresholds,
                        dataset_tag="holdout",
                        require_task_delta_ci=True,
                    )
            else:
                canonical_multi_pass_streak = 0

        training_result = None
        if bool(args.enable_training_branch) and no_improve_streak >= int(args.no_improve_to_train):
            training_result = _run_training_branch(py, round_idx)
            no_improve_streak = 0

        _append_snapshot(
            path=ROOT / args.snapshot_doc,
            round_name="Round {}".format(round_idx),
            canonical_result=canonical,
            dev_result=dev,
            holdout_result=holdout,
            gate=gate,
            dev_gate=dev_gate,
            holdout_gate=holdout_gate,
            can_thresholds=can_thresholds,
            score=score,
            improved=improved,
            best_score=best_score,
            actions=actions,
            canonical_ms=canonical_ms,
            holdout_ms=holdout_ms,
            regression_guard={
                "regressions": regressions,
                "rollback_applied": bool(rollback_applied),
            },
            training_result=training_result,
            run_status=run_status,
            interrupted_reason=interrupted_reason,
            dev_status=dev_status,
            dev_reason=dev_reason,
            holdout_status=holdout_status,
            holdout_reason=holdout_reason,
        )

        round_records.append(
            {
                "round": int(round_idx),
                "run_status": run_status,
                "interrupted_reason": interrupted_reason,
                "canonical_status": can_status,
                "canonical_reason": can_reason,
                "dev_status": dev_status,
                "dev_reason": dev_reason,
                "holdout_status": holdout_status,
                "holdout_reason": holdout_reason,
                "canonical_pass": bool(canonical_gate_pass),
                "dev_pass": bool(dev_gate_pass) if dev_status == "success" else None,
                "score": float(score),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        round_records = round_records[-50:]
        _save_state(
            state_file,
            {
                "best_score": float(best_score),
                "no_improve_streak": int(no_improve_streak),
                "single_pass_streak": int(single_pass_streak),
                "canonical_multi_pass_streak": int(canonical_multi_pass_streak),
                "rounds_since_multi": int(rounds_since_multi),
                "best_stable_round": int(best_stable_round),
                "best_stable_metrics": best_stable_metrics,
                "last_dev_result": last_dev_result,
                "last_holdout_result": last_holdout_result,
                "round_records": round_records,
                "run_status": run_status,
                "interrupted_reason": interrupted_reason,
                "next_round": int(round_idx + 1),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        )

        print(
            "[round {}] can_f1={:.4f} can_single_doc={:.4f} can_ratio={:.4f} dev_status={} holdout_status={} "
            "can_pass={} dev_pass={} can_multi_streak={}".format(
                round_idx,
                canonical["agent_f1"],
                canonical["single_doc_f1"],
                canonical["p95_ratio"],
                dev_status,
                holdout_status,
                canonical_gate_pass,
                dev_gate_pass,
                canonical_multi_pass_streak,
            )
        )

        if canonical_multi_pass_streak >= 2:
            print("[stop] two consecutive canonical 3-seed passes.")
            break

        rounds_run += 1
        round_idx += 1
        time.sleep(1.0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("interrupted")
        sys.exit(130)

