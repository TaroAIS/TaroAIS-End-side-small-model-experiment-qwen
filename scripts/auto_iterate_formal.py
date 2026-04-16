#!/usr/bin/env python3
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def now_ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def sf(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def si(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def read_csv(path):
    p = Path(path)
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_state(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(path, state):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def run_cmd(cmd, timeout_s=None):
    print("[run] {}".format(" ".join([str(x) for x in cmd])))
    env = os.environ.copy()
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    env.setdefault("HF_DATASETS_OFFLINE", "1")
    subprocess.run(cmd, cwd=str(ROOT), env=env, check=True, timeout=timeout_s)


def copy_file(src, dst):
    src_p = Path(src)
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_p, dst_p)


def rel_path(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except Exception:
        try:
            return str(Path(path).relative_to(ROOT))
        except Exception:
            return str(path)


def acquire_lock(path):
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None, lock_path
    payload = {
        "pid": os.getpid(),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return lock_path, lock_path


def release_lock(lock_handle):
    if not lock_handle:
        return
    try:
        Path(lock_handle).unlink(missing_ok=True)
    except Exception:
        pass


def parse_report(report_dir, baseline_stem, agent_stem):
    metrics = read_csv(Path(report_dir) / "metrics_table.csv")
    tasks = read_csv(Path(report_dir) / "task_metrics.csv")
    base = next((r for r in metrics if baseline_stem in r.get("method", "")), {})
    agent = next((r for r in metrics if agent_stem in r.get("method", "")), {})
    base_name = base.get("method", "")
    agent_name = agent.get("method", "")

    def task_f1(method_name, task):
        row = next((r for r in tasks if r.get("method", "") == method_name and r.get("task", "") == task), {})
        return sf(row.get("f1", 0.0))

    base_p95 = sf(base.get("p95_latency_ms", 0.0))
    agent_p95 = sf(agent.get("p95_latency_ms", 0.0))
    return {
        "baseline_method": base_name,
        "agent_method": agent_name,
        "baseline_f1": sf(base.get("f1", 0.0)),
        "agent_f1": sf(agent.get("f1", 0.0)),
        "single_doc_f1": task_f1(agent_name, "single_doc_qa"),
        "multi_doc_f1": task_f1(agent_name, "multi_doc_qa"),
        "code_f1": task_f1(agent_name, "code_qa"),
        "baseline_code_f1": task_f1(base_name, "code_qa"),
        "p95_ratio": (agent_p95 / base_p95) if base_p95 > 0 else 99.0,
        "agent_avg_steps": sf(agent.get("avg_steps", 0.0)),
        "agent_avg_retrieval": sf(agent.get("avg_retrieval", 0.0)),
        "agent_oom": si(agent.get("oom_count", 0)),
        "report_dir": str(report_dir),
    }


def gate(metrics, thresholds):
    return {
        "overall_pass": sf(metrics.get("agent_f1", 0.0)) >= sf(thresholds["overall_f1"]),
        "single_doc_pass": sf(metrics.get("single_doc_f1", 0.0)) >= sf(thresholds["single_doc_f1"]),
        "ratio_pass": sf(metrics.get("p95_ratio", 0.0)) <= sf(thresholds["p95_ratio"]),
        "oom_pass": si(metrics.get("agent_oom", 0)) == 0,
    }


def gate_ok(g):
    return bool(g["overall_pass"] and g["single_doc_pass"] and g["ratio_pass"] and g["oom_pass"])


def score(metrics, thresholds):
    quality = (
        0.45 * sf(metrics.get("agent_f1", 0.0))
        + 0.25 * sf(metrics.get("single_doc_f1", 0.0))
        + 0.15 * sf(metrics.get("multi_doc_f1", 0.0))
        + 0.15 * sf(metrics.get("code_f1", 0.0))
    )
    penalty = (
        0.35 * max(0.0, sf(thresholds["overall_f1"]) - sf(metrics.get("agent_f1", 0.0)))
        + 0.35 * max(0.0, sf(thresholds["single_doc_f1"]) - sf(metrics.get("single_doc_f1", 0.0)))
        + 0.20 * max(0.0, sf(metrics.get("p95_ratio", 0.0)) - sf(thresholds["p95_ratio"]))
        + 0.10 * si(metrics.get("agent_oom", 0))
    )
    return float(quality - penalty)


def ensure_anchor(py, baseline_config, dataset, out_path, run_mode, retrieval_scope, seed):
    out = ROOT / out_path
    if out.exists():
        return "reuse"
    run_cmd(
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
    return "create"


def run_single(py, config, dataset, baseline_anchor, seed, run_mode, retrieval_scope, round_idx, dataset_tag):
    ts = now_ts()
    agent_pred = ROOT / "results" / "edge_agent_formal_auto_r{}_{}_{}.jsonl".format(round_idx, dataset_tag, ts)
    report_dir = ROOT / "report" / "formal_auto_r{}_{}_{}".format(round_idx, dataset_tag, ts)
    run_cmd(
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
    run_cmd(
        [
            py,
            "evaluate.py",
            "--gold",
            dataset,
            "--pred",
            str(ROOT / baseline_anchor),
            str(agent_pred),
            "--out_dir",
            str(report_dir),
            "--run_mode",
            run_mode,
            "--task_breakdown",
        ]
    )
    return parse_report(report_dir, Path(baseline_anchor).stem, agent_pred.stem)


def run_multi_seed(py, config, baseline_config, dataset, thresholds, seeds, run_mode, retrieval_scope, round_idx):
    results = []
    for seed in seeds:
        ts = now_ts()
        baseline_pred = ROOT / "results" / "baseline_rag_formal_auto_r{}_s{}_{}.jsonl".format(round_idx, seed, ts)
        agent_pred = ROOT / "results" / "edge_agent_formal_auto_r{}_s{}_{}.jsonl".format(round_idx, seed, ts)
        report_dir = ROOT / "report" / "formal_auto_r{}_s{}_{}".format(round_idx, seed, ts)
        run_cmd(
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
        run_cmd(
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
        run_cmd(
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
                "--task_breakdown",
            ]
        )
        results.append(parse_report(report_dir, baseline_pred.stem, agent_pred.stem))
    mean_f1 = sum(x["agent_f1"] for x in results) / float(len(results) or 1)
    mean_single = sum(x["single_doc_f1"] for x in results) / float(len(results) or 1)
    mean_ratio = sum(x["p95_ratio"] for x in results) / float(len(results) or 1)
    oom_sum = sum(int(x["agent_oom"]) for x in results)
    return {
        "pass": bool(mean_f1 >= sf(thresholds["overall_f1"]) and mean_single >= sf(thresholds["single_doc_f1"]) and mean_ratio <= sf(thresholds["p95_ratio"]) and oom_sum == 0),
        "mean_agent_f1": mean_f1,
        "mean_single_doc_f1": mean_single,
        "mean_ratio": mean_ratio,
        "oom_sum": oom_sum,
    }


def _flatten_cfg(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = "{}.{}".format(prefix, key) if prefix else str(key)
            out.update(_flatten_cfg(value, child))
        return out
    if isinstance(obj, list):
        if all(isinstance(x, (str, int, float, bool)) or x is None for x in obj) and len(obj) <= 8:
            out[prefix] = obj
        else:
            out[prefix] = "<list:{}>".format(len(obj))
        return out
    out[prefix] = obj
    return out


def _fmt_cfg_value(value):
    if isinstance(value, float):
        return "{:.4f}".format(value)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return "null"
    return str(value)


def summarize_config_diff(prev_path, current_path, max_items=12):
    current_cfg = yaml.safe_load(Path(current_path).read_text(encoding="utf-8")) or {}
    current_flat = _flatten_cfg(current_cfg)
    prev_flat = {}
    if prev_path and Path(prev_path).exists():
        prev_cfg = yaml.safe_load(Path(prev_path).read_text(encoding="utf-8")) or {}
        prev_flat = _flatten_cfg(prev_cfg)
    keys = sorted(set(prev_flat.keys()) | set(current_flat.keys()))
    lines = []
    for key in keys:
        old = prev_flat.get(key, "<missing>")
        new = current_flat.get(key, "<missing>")
        if old == new:
            continue
        if old == "<missing>":
            lines.append("added `{}` = `{}`".format(key, _fmt_cfg_value(new)))
        elif new == "<missing>":
            lines.append("removed `{}` (was `{}`)".format(key, _fmt_cfg_value(old)))
        else:
            lines.append("`{}`: `{}` -> `{}`".format(key, _fmt_cfg_value(old), _fmt_cfg_value(new)))
    if not lines:
        return ["no material config delta vs previous evaluated round"]
    if len(lines) > max_items:
        remainder = len(lines) - max_items
        lines = lines[:max_items] + ["... {} more config deltas omitted".format(remainder)]
    return lines


def extract_experiment_meta(config_path):
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    exp = cfg.get("experiment", {}) or {}
    model = cfg.get("model", {}) or {}
    return {
        "profile": exp.get("profile", ""),
        "objective": exp.get("objective", ""),
        "model_name": model.get("name_or_path", ""),
    }


def apply_one_factor(config_path, failure_mode, dry_run=False):
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    retrieval = cfg.setdefault("retrieval", {})
    hybrid = retrieval.setdefault("hybrid", {})
    agent_cfg = cfg.setdefault("agent", {})
    early = agent_cfg.setdefault("early_stop", {})
    budget = agent_cfg.setdefault("decoding_budget", {})
    caps = budget.setdefault("task_caps", {})
    task_overrides = agent_cfg.setdefault("task_overrides", {})
    single_doc = task_overrides.setdefault("single_doc_qa", {})
    multi_doc = task_overrides.setdefault("multi_doc_qa", {})
    code_qa = task_overrides.setdefault("code_qa", {})

    action = "no_change"
    if failure_mode == "single_doc_recall":
        old = si(single_doc.get("top_k_init", 3), 3)
        single_doc["top_k_init"] = min(5, old + 1)
        action = "single_doc.top_k_init {}->{}".format(old, single_doc["top_k_init"])
    elif failure_mode == "tail_latency":
        old = si(budget.get("default_max_new_tokens", 160), 160)
        budget["default_max_new_tokens"] = max(128, old - 16)
        action = "decoding_budget.default_max_new_tokens {}->{}".format(old, budget["default_max_new_tokens"])
    elif failure_mode == "multi_doc_recall":
        old = si(multi_doc.get("top_k_iter", 1), 1)
        multi_doc["top_k_iter"] = min(2, old + 1)
        action = "multi_doc.top_k_iter {}->{}".format(old, multi_doc["top_k_iter"])
    elif failure_mode == "code_recall":
        old = si(code_qa.get("top_k_init", 2), 2)
        code_qa["top_k_init"] = min(4, old + 1)
        action = "code_qa.top_k_init {}->{}".format(old, code_qa["top_k_init"])
    elif failure_mode == "oom_guard":
        old = si(caps.get("multi_doc_qa", 176), 176)
        caps["multi_doc_qa"] = max(144, old - 16)
        action = "task_caps.multi_doc_qa {}->{}".format(old, caps["multi_doc_qa"])
    else:
        old = si(hybrid.get("max_candidates", 10), 10)
        hybrid["max_candidates"] = max(8, old - 1)
        action = "retrieval.hybrid.max_candidates {}->{}".format(old, hybrid["max_candidates"])
        if action == "retrieval.hybrid.max_candidates {}->{}".format(old, hybrid["max_candidates"]) and old == hybrid["max_candidates"]:
            old = si(early.get("single_doc_max_steps", 2), 2)
            early["single_doc_max_steps"] = min(3, old + 1)
            action = "early_stop.single_doc_max_steps {}->{}".format(old, early["single_doc_max_steps"])

    if not dry_run:
        Path(config_path).write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return action
    return cfg, action


def append_snapshot(path, round_idx, summary):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("# 24. 实验快照（当前）\n", encoding="utf-8")
    text = p.read_text(encoding="utf-8")
    lines = [
        "",
        "## Round {} ({})".format(round_idx, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "",
        "- config_profile: `{}`".format(summary.get("config_profile", "")),
        "- config_objective: `{}`".format(summary.get("config_objective", "")),
        "- config_model: `{}`".format(summary.get("config_model", "")),
        "- config_snapshot: `{}`".format(summary.get("config_snapshot", "")),
        "- promotion_ready: `{}`".format("pass" if summary["promotion_ready"] else "fail"),
        "- canonical_status: `{}`".format(summary["canonical_status"]),
        "- failure_mode: `{}`".format(summary["failure_mode"]),
        "- score: `{:.4f}`".format(summary["score"]),
        "- best_score: `{:.4f}`".format(summary["best_score"]),
        "- next_action: `{}`".format(summary["next_action"]),
        "",
        "### Config Diff",
    ]
    for item in summary.get("config_diff", []):
        lines.append("- {}".format(item))
    lines.extend(
        [
            "",
            "### Four-Route References",
            "| route | reference |",
            "| --- | --- |",
        ]
    )
    for route, reference in summary.get("control_refs", []):
        lines.append("| {} | `{}` |".format(route, reference))
    lines.append("")
    lines.extend(
        [
            "### Current Agent Reports",
            "| split | report_dir |",
            "| --- | --- |",
        ]
    )
    for title, result in [
        ("dev100", summary["dev"]),
        ("holdout100", summary["holdout"]),
        ("quickgate30", summary["quick"]),
        ("canonical", summary["canonical"]),
    ]:
        lines.append("| {} | `{}` |".format(title, rel_path(result.get("report_dir", "-"))))
    lines.append("")
    for title, result in [
        ("dev100", summary["dev"]),
        ("holdout100", summary["holdout"]),
        ("quickgate30", summary["quick"]),
        ("canonical", summary["canonical"]),
    ]:
        lines.extend(
            [
                "### {}".format(title),
                "| item | value |",
                "| --- | ---: |",
                "| F1 | {:.4f} |".format(result["agent_f1"]),
                "| single_doc | {:.4f} |".format(result["single_doc_f1"]),
                "| multi_doc | {:.4f} |".format(result["multi_doc_f1"]),
                "| code | {:.4f} |".format(result["code_f1"]),
                "| p95 ratio | {:.4f} |".format(result["p95_ratio"]),
                "| oom | {} |".format(int(result["agent_oom"])),
                "",
            ]
        )
    if summary.get("multiseed"):
        ms = summary["multiseed"]
        lines.extend(
            [
                "### canonical 3-seed confirm",
                "- pass: `{}`".format("pass" if ms["pass"] else "fail"),
                "- mean F1: `{:.4f}`".format(ms["mean_agent_f1"]),
                "- mean single_doc: `{:.4f}`".format(ms["mean_single_doc_f1"]),
                "- mean p95 ratio: `{:.4f}`".format(ms["mean_ratio"]),
                "",
            ]
        )
    p.write_text(text + "\n".join(lines) + "\n", encoding="utf-8")


def build_control_refs(args):
    return [
        ("baseline_rag_4b_anchor_canonical", args.canonical_baseline_anchor),
        ("baseline_budget_matched_4b", "results/baseline_budget_matched.jsonl"),
        ("baseline_single_round_strong_4b", "results/baseline_single_round_strong.jsonl"),
        ("edge_agent_4b_default_config", args.config),
    ]


def save_round_config_snapshot(config_path, round_idx, out_dir):
    out = Path(out_dir) / "round_{:02d}_evaluated.yaml".format(int(round_idx))
    copy_file(config_path, out)
    return out


def main():
    ap = argparse.ArgumentParser(description="4B canonical mainline auto-iteration.")
    ap.add_argument("--python", default=str(ROOT / ".venv" / "Scripts" / "python.exe"))
    ap.add_argument("--config", default="configs/agent.yaml")
    ap.add_argument("--baseline_config", default="configs/baseline_rag.yaml")
    ap.add_argument("--canonical_dataset", default="data/main_eval/longbench_3tasks_test.jsonl")
    ap.add_argument("--dev_dataset", default="data/main_eval/longbench_3tasks_dev100.jsonl")
    ap.add_argument("--holdout_dataset", default="data/main_eval/longbench_3tasks_holdout100.jsonl")
    ap.add_argument("--quickgate_dataset", default="data/main_eval/longbench_3tasks_quickgate30.jsonl")
    ap.add_argument("--run_mode", default="formal", choices=["smoke", "formal"])
    ap.add_argument("--retrieval_scope", default="sample", choices=["sample", "global"])
    ap.add_argument("--single_seed", type=int, default=42)
    ap.add_argument("--multi_seeds", nargs="+", default=["42", "123", "2026"])
    ap.add_argument("--snapshot_doc", default="docs/24_实验快照_当前.md")
    ap.add_argument("--state_path", default="results/auto_iterate_state.json")
    ap.add_argument("--last_good_config", default="results/last_good_config.yaml")
    ap.add_argument("--round_config_dir", default="results/round_configs")
    ap.add_argument("--lock_path", default="results/auto_iterate_formal.lock")
    ap.add_argument("--canonical_baseline_anchor", default="results/baseline_rag_formal_anchor_4b_canonical.jsonl")
    ap.add_argument("--dev_baseline_anchor", default="results/baseline_rag_formal_anchor_4b_dev100.jsonl")
    ap.add_argument("--holdout_baseline_anchor", default="results/baseline_rag_formal_anchor_4b_holdout100.jsonl")
    ap.add_argument("--quickgate_baseline_anchor", default="results/baseline_rag_formal_anchor_4b_quickgate30.jsonl")
    ap.add_argument("--target_overall_f1", type=float, default=0.34)
    ap.add_argument("--target_single_doc_f1", type=float, default=0.29)
    ap.add_argument("--target_p95_ratio", type=float, default=1.8)
    ap.add_argument("--dev_target_overall_f1", type=float, default=0.31)
    ap.add_argument("--dev_target_single_doc_f1", type=float, default=0.27)
    ap.add_argument("--dev_target_p95_ratio", type=float, default=1.95)
    ap.add_argument("--holdout_target_overall_f1", type=float, default=0.32)
    ap.add_argument("--holdout_target_single_doc_f1", type=float, default=0.28)
    ap.add_argument("--holdout_target_p95_ratio", type=float, default=1.9)
    ap.add_argument("--quickgate_target_overall_f1", type=float, default=0.32)
    ap.add_argument("--quickgate_target_single_doc_f1", type=float, default=0.28)
    ap.add_argument("--quickgate_target_p95_ratio", type=float, default=1.8)
    ap.add_argument("--min_score_delta", type=float, default=0.002)
    ap.add_argument("--start_round", type=int, default=1)
    ap.add_argument("--max_rounds", type=int, default=0)
    args = ap.parse_args()

    lock_handle, lock_path = acquire_lock(ROOT / args.lock_path)
    if not lock_handle:
        print("[skip] another auto_iterate_formal instance is already running: {}".format(lock_path))
        return

    try:
        py = args.python
        can_t = {"overall_f1": args.target_overall_f1, "single_doc_f1": args.target_single_doc_f1, "p95_ratio": args.target_p95_ratio}
        dev_t = {"overall_f1": args.dev_target_overall_f1, "single_doc_f1": args.dev_target_single_doc_f1, "p95_ratio": args.dev_target_p95_ratio}
        hold_t = {"overall_f1": args.holdout_target_overall_f1, "single_doc_f1": args.holdout_target_single_doc_f1, "p95_ratio": args.holdout_target_p95_ratio}
        quick_t = {"overall_f1": args.quickgate_target_overall_f1, "single_doc_f1": args.quickgate_target_single_doc_f1, "p95_ratio": args.quickgate_target_p95_ratio}

        for dataset, anchor in [
            (args.dev_dataset, args.dev_baseline_anchor),
            (args.holdout_dataset, args.holdout_baseline_anchor),
            (args.quickgate_dataset, args.quickgate_baseline_anchor),
        ]:
            ensure_anchor(py, args.baseline_config, dataset, anchor, args.run_mode, args.retrieval_scope, args.single_seed)

        if not (ROOT / args.last_good_config).exists():
            copy_file(ROOT / args.config, ROOT / args.last_good_config)

        state = load_state(ROOT / args.state_path)
        best_score = sf(state.get("best_score", -1e9))
        no_improve_streak = si(state.get("no_improve_streak", 0))
        canonical_pass_streak = si(state.get("canonical_pass_streak", 0))
        round_idx = max(args.start_round, si(state.get("next_round", args.start_round)))

        rounds_run = 0
        while True:
            if args.max_rounds > 0 and rounds_run >= args.max_rounds:
                break

            round_config_snapshot = save_round_config_snapshot(ROOT / args.config, round_idx, ROOT / args.round_config_dir)
            prev_round_snapshot = Path(ROOT / args.round_config_dir) / "round_{:02d}_evaluated.yaml".format(max(0, round_idx - 1))
            config_meta = extract_experiment_meta(round_config_snapshot)
            config_diff = summarize_config_diff(prev_round_snapshot if prev_round_snapshot.exists() else None, round_config_snapshot)

            dev = run_single(py, args.config, args.dev_dataset, args.dev_baseline_anchor, args.single_seed, args.run_mode, args.retrieval_scope, round_idx, "dev")
            holdout = run_single(py, args.config, args.holdout_dataset, args.holdout_baseline_anchor, args.single_seed, args.run_mode, args.retrieval_scope, round_idx, "holdout")
            quick = run_single(py, args.config, args.quickgate_dataset, args.quickgate_baseline_anchor, args.single_seed, args.run_mode, args.retrieval_scope, round_idx, "quickgate")

            dev_gate = gate(dev, dev_t)
            holdout_gate = gate(holdout, hold_t)
            quick_gate = gate(quick, quick_t)
            promotion_ready = bool(gate_ok(dev_gate) and gate_ok(holdout_gate) and gate_ok(quick_gate))

            canonical_status = "skipped_promotion_guard"
            canonical = state.get("last_canonical_result") or quick
            if promotion_ready:
                ensure_anchor(
                    py,
                    args.baseline_config,
                    args.canonical_dataset,
                    args.canonical_baseline_anchor,
                    args.run_mode,
                    args.retrieval_scope,
                    args.single_seed,
                )
                canonical = run_single(py, args.config, args.canonical_dataset, args.canonical_baseline_anchor, args.single_seed, args.run_mode, args.retrieval_scope, round_idx, "can")
                canonical_status = "success"
            canonical_gate = gate(canonical, can_t)

            current = canonical if canonical_status == "success" else quick
            current_t = can_t if canonical_status == "success" else quick_t
            active_gate = canonical_gate if canonical_status == "success" else quick_gate
            current_score = score(current, current_t)
            improved = (current_score - best_score) >= args.min_score_delta
            if improved:
                best_score = current_score
                no_improve_streak = 0
            else:
                no_improve_streak += 1

            if not active_gate["oom_pass"]:
                failure_mode = "oom_guard"
            elif not active_gate["ratio_pass"]:
                failure_mode = "tail_latency"
            elif not active_gate["single_doc_pass"]:
                failure_mode = "single_doc_recall"
            elif current["multi_doc_f1"] <= min(current["single_doc_f1"], current["code_f1"]):
                failure_mode = "multi_doc_recall"
            elif current["code_f1"] < current.get("baseline_code_f1", 0.0):
                failure_mode = "code_recall"
            else:
                failure_mode = "slow_plateau"

            next_action = "keep_current_config"
            multiseed = None
            next_cfg = None
            rollback_needed = bool((not improved) and current_score < (best_score - 0.03))
            if rollback_needed:
                canonical_pass_streak = 0
                next_action = "rollback_to_last_good_config"
            elif canonical_status == "success" and gate_ok(canonical_gate):
                canonical_pass_streak += 1
                copy_file(ROOT / args.config, ROOT / args.last_good_config)
                state["last_canonical_result"] = canonical
                if canonical_pass_streak >= 2:
                    multiseed = run_multi_seed(py, args.config, args.baseline_config, args.canonical_dataset, can_t, [int(x) for x in args.multi_seeds], args.run_mode, args.retrieval_scope, round_idx)
            else:
                canonical_pass_streak = 0
                next_cfg, next_action = apply_one_factor(ROOT / args.config, failure_mode, dry_run=True)

            summary = {
                "promotion_ready": promotion_ready,
                "canonical_status": canonical_status,
                "failure_mode": failure_mode,
                "score": current_score,
                "best_score": best_score,
                "next_action": next_action,
                "dev": dev,
                "holdout": holdout,
                "quick": quick,
                "canonical": canonical,
                "multiseed": multiseed,
                "config_profile": config_meta.get("profile", ""),
                "config_objective": config_meta.get("objective", ""),
                "config_model": config_meta.get("model_name", ""),
                "config_snapshot": rel_path(round_config_snapshot),
                "config_diff": config_diff,
                "control_refs": build_control_refs(args),
            }
            append_snapshot(ROOT / args.snapshot_doc, round_idx, summary)

            if rollback_needed:
                copy_file(ROOT / args.last_good_config, ROOT / args.config)
            elif next_cfg is not None:
                Path(ROOT / args.config).write_text(yaml.safe_dump(next_cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")

            state.update(
                {
                    "best_score": best_score,
                    "no_improve_streak": no_improve_streak,
                    "canonical_pass_streak": canonical_pass_streak,
                    "next_round": round_idx + 1,
                    "last_canonical_result": canonical,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            save_state(ROOT / args.state_path, state)

            print("[round {}] promotion={} canonical_status={} score={:.4f} next={}".format(round_idx, promotion_ready, canonical_status, current_score, next_action))

            if multiseed and multiseed["pass"]:
                print("[stop] canonical 3-seed confirm passed.")
                break
            if no_improve_streak >= 2:
                print("[stop] two consecutive rounds without significant improvement.")
                break

            round_idx += 1
            rounds_run += 1
            time.sleep(1.0)
    finally:
        release_lock(lock_handle)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("interrupted")
        sys.exit(130)
