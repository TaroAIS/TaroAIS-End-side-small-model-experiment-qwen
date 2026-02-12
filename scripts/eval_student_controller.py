#!/usr/bin/env python3
import argparse
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.edge_reasoning_agent import EdgeReasoningAgent
from agent.prompts import build_agent_prompt, format_evidence_chunks
from llm.driver_hf import HFLLMDriver
from llm.driver_local import LocalLLMDriver
from metrics.qa_metrics import best_over_gold
from retrieval.chunking import build_chunks_from_documents
from retrieval.index_faiss import RetrievalIndex, build_and_save_index
from utils.io import dump_jsonl, ensure_dir, load_jsonl, load_yaml, read_json, write_json
from utils.runtime import project_root, schema_path
from utils.schema import validate_records


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


def _tokenize(text):
    return re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]", (text or "").lower())


def _keyword_from_question(question):
    toks = [t for t in _tokenize(question) if len(t) >= 1]
    return " ".join(toks[:4]) if toks else "关键信息"


def _build_driver(cfg):
    backend = cfg.get("model", {}).get("backend", "local")
    if backend == "hf":
        return HFLLMDriver(cfg)
    return LocalLLMDriver(cfg)


def _teacher_controller_from_driver(driver):
    def controller(question, evidence, step, max_steps, sample):
        prompt = build_agent_prompt(
            question=question,
            evidence_text=evidence,
            step=step,
            max_steps=max_steps,
            memory_strategy="fact_memory",
            note="teacher_behavior_eval",
            facts_text="",
        )
        return driver.generate(prompt, expect_protocol=True)

    return controller


def _student_controller_from_checkpoint(checkpoint_dir):
    rules_path = Path(checkpoint_dir) / "student_controller_rules.json"
    rules = {}
    if rules_path.exists():
        try:
            rules = read_json(rules_path)
        except Exception:
            rules = {}

    fitted = rules.get("fitted_stats", {})
    by_task = fitted.get("by_task_policy", {}) if isinstance(fitted, dict) else {}

    def controller(question, evidence, step, max_steps, sample):
        task = sample.get("task", "")
        if step >= max_steps:
            best = (evidence or "").strip().split("\n")
            ans = best[0] if best and best[0] else "信息不足"
            return "<final>{}</final>".format(ans[:200])

        if task in by_task:
            action = by_task[task].get("default_action", "final")
            if action == "search" and step == 1:
                return "<search>{}</search>".format(_keyword_from_question(question))

        if task == "multi_doc_qa" and step == 1:
            return "<search>{}</search>".format(_keyword_from_question(question))

        q_toks = _tokenize(question)
        overlap = 0
        low = (evidence or "").lower()
        for t in q_toks:
            if t in low:
                overlap += 1
        if overlap < 2 and step == 1:
            return "<search>{}</search>".format(_keyword_from_question(question))

        best = (evidence or "").strip().split("\n")
        ans = best[0] if best and best[0] else "信息不足"
        return "<final>{}</final>".format(ans[:200])

    return controller, rules


def _macro_f1_binary(y_true, y_pred):
    labels = ["search", "final"]
    f1s = []
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        if tp == 0 and (fp > 0 or fn > 0):
            f1s.append(0.0)
            continue
        if tp == 0 and fp == 0 and fn == 0:
            f1s.append(1.0)
            continue
        p = tp / float(tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / float(tp + fn) if (tp + fn) > 0 else 0.0
        if p + r <= 0:
            f1s.append(0.0)
        else:
            f1s.append(2 * p * r / (p + r))
    return sum(f1s) / float(len(f1s))


def _control_eval(dataset_rows, controller_fn):
    y_true = []
    y_pred = []
    hit_n = 0
    hit_d = 0

    for s in dataset_rows:
        gold_tag = "search" if s.get("task") == "multi_doc_qa" else "final"
        docs = s.get("documents", [])
        chunks = build_chunks_from_documents(
            docs, sample_id=s.get("id", "sample"), chunk_size=512, overlap=128
        )
        idx = RetrievalIndex(index_type="lexical")
        idx.build(chunks)

        evidence_chunks = idx.search(s.get("question", ""), top_k=3)
        evidence = format_evidence_chunks(
            evidence_chunks,
            injection_cfg={"enable": False, "quote_chunks": False, "label_as_evidence": False},
        )
        out = controller_fn(
            question=s.get("question", ""),
            evidence=evidence,
            step=1,
            max_steps=4,
            sample=s,
        )
        keyword = ""
        m = re.match(r"^\s*<search>(.*?)</search>\s*$", (out or "").strip(), flags=re.S | re.I)
        if m:
            pred_tag = "search"
            keyword = m.group(1).strip()
        else:
            pred_tag = "final"

        y_true.append(gold_tag)
        y_pred.append(pred_tag)

        if pred_tag == "search":
            hit_d += 1
            hits = idx.search(keyword or s.get("question", ""), top_k=1)
            gold = s.get("answer", "")
            if hits and gold and gold in hits[0].get("text", ""):
                hit_n += 1

    trigger_acc = sum(1 for t, p in zip(y_true, y_pred) if t == p) / float(len(y_true) or 1)
    macro_f1 = _macro_f1_binary(y_true, y_pred)
    keyword_hit_rate = hit_n / float(hit_d or 1)
    return {
        "trigger_acc": trigger_acc,
        "macro_f1": macro_f1,
        "keyword_hit_rate": keyword_hit_rate,
    }


def _end2end_eval(dataset_rows, agent_cfg, controller_fn=None):
    driver = _build_driver(agent_cfg)
    idx_dir = project_root() / "data" / "student_eval_index"
    out_chunk = idx_dir / "chunks.jsonl"
    _, index = build_and_save_index(
        dataset_rows,
        out_chunk_path=str(out_chunk),
        index_dir=str(idx_dir),
        chunk_size=agent_cfg.get("retrieval", {}).get("chunk_size", 512),
        chunk_overlap=agent_cfg.get("retrieval", {}).get("chunk_overlap", 128),
        embedding_model=agent_cfg.get("retrieval", {}).get("embedding_model", "sentence-transformers"),
        index_type=agent_cfg.get("retrieval", {}).get("index", "faiss"),
    )

    agent = EdgeReasoningAgent(agent_cfg, driver, index, controller_fn=controller_fn)

    f1s = []
    ems = []
    retr = []
    lat = []
    raw = []
    for s in dataset_rows:
        r, _ = agent.run_sample(s)
        em, f1 = best_over_gold(r.get("pred", ""), s.get("answer", ""))
        f1s.append(f1)
        ems.append(em)
        retr.append(r.get("n_retrieval", 0))
        lat.append(r.get("latency_ms", {}).get("total", 0.0))
        raw.append(r)

    n = float(len(dataset_rows) or 1)
    return {
        "em": sum(ems) / n,
        "f1": sum(f1s) / n,
        "avg_retrieval": sum(retr) / n,
        "avg_latency_ms": sum(lat) / n,
        "rows": raw,
    }


def _task_breakdown_from_rows(model_name, rows, task_map):
    grouped = {}
    for r in rows:
        sid = r.get("id", "")
        task = task_map.get(sid, "unknown")
        if task not in grouped:
            grouped[task] = []
        grouped[task].append(r)

    out = []
    for task in sorted(grouped.keys()):
        xs = grouped[task]
        n = float(len(xs) or 1)
        ems = []
        f1s = []
        retr = []
        lat = []
        for r in xs:
            em, f1 = best_over_gold(r.get("pred", ""), r.get("gold", ""))
            ems.append(em)
            f1s.append(f1)
            retr.append(_safe_float(r.get("n_retrieval", 0)))
            lat.append(_safe_float(r.get("latency_ms", {}).get("total", 0.0)))
        out.append(
            {
                "model": model_name,
                "task": task,
                "n_samples": int(len(xs)),
                "em": sum(ems) / n,
                "f1": sum(f1s) / n,
                "avg_retrieval": sum(retr) / n,
                "avg_latency_ms": sum(lat) / n,
            }
        )
    return out


def _key_summary(task_rows, model_name, key_tasks, key_agg):
    selected = [x for x in task_rows if x.get("model") == model_name and x.get("task") in set(key_tasks)]
    if not selected:
        return {
            "model": model_name,
            "key_tasks": "|".join(key_tasks),
            "key_agg": key_agg,
            "n_tasks": 0,
            "n_samples": 0,
            "em": 0.0,
            "f1": 0.0,
            "avg_retrieval": 0.0,
            "avg_latency_ms": 0.0,
        }

    if key_agg == "micro":
        total_n = sum([_safe_int(x.get("n_samples", 0)) for x in selected]) or 1
        em = sum([_safe_float(x.get("em", 0.0)) * _safe_int(x.get("n_samples", 0)) for x in selected]) / float(total_n)
        f1 = sum([_safe_float(x.get("f1", 0.0)) * _safe_int(x.get("n_samples", 0)) for x in selected]) / float(total_n)
        avg_retrieval = sum(
            [_safe_float(x.get("avg_retrieval", 0.0)) * _safe_int(x.get("n_samples", 0)) for x in selected]
        ) / float(total_n)
        avg_latency = sum(
            [_safe_float(x.get("avg_latency_ms", 0.0)) * _safe_int(x.get("n_samples", 0)) for x in selected]
        ) / float(total_n)
        n_tasks = len(sorted(set([x.get("task", "") for x in selected])))
        n_samples = total_n
    else:
        n = float(len(selected))
        em = sum([_safe_float(x.get("em", 0.0)) for x in selected]) / n
        f1 = sum([_safe_float(x.get("f1", 0.0)) for x in selected]) / n
        avg_retrieval = sum([_safe_float(x.get("avg_retrieval", 0.0)) for x in selected]) / n
        avg_latency = sum([_safe_float(x.get("avg_latency_ms", 0.0)) for x in selected]) / n
        n_tasks = len(selected)
        n_samples = sum([_safe_int(x.get("n_samples", 0)) for x in selected])

    return {
        "model": model_name,
        "key_tasks": "|".join(key_tasks),
        "key_agg": key_agg,
        "n_tasks": int(n_tasks),
        "n_samples": int(n_samples),
        "em": em,
        "f1": f1,
        "avg_retrieval": avg_retrieval,
        "avg_latency_ms": avg_latency,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate student controller: behavior + end-to-end")
    parser.add_argument("--agent_config", default="configs/agent.yaml")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--checkpoint", default="checkpoints/student")
    parser.add_argument("--out_dir", default="report_student")
    parser.add_argument("--run_mode", choices=["smoke", "formal"], default="formal")
    parser.add_argument("--task_breakdown", action="store_true", default=True)
    parser.add_argument("--no_task_breakdown", dest="task_breakdown", action="store_false")
    parser.add_argument("--key_tasks", nargs="+", default=["multi_doc_qa", "code_qa"])
    parser.add_argument("--key_agg", choices=["macro", "micro"], default="macro")
    args = parser.parse_args()

    ensure_dir(args.out_dir)

    agent_cfg = load_yaml(args.agent_config)
    agent_cfg = dict(agent_cfg)
    agent_cfg["runtime"] = {"run_mode": args.run_mode}
    rows = load_jsonl(args.dataset)
    validate_records(rows, schema_path("dataset.schema.json"), context_prefix="dataset")

    teacher_driver = _build_driver(agent_cfg)
    teacher_controller = _teacher_controller_from_driver(teacher_driver)
    student_controller_fn, rules = _student_controller_from_checkpoint(args.checkpoint)

    teacher_behavior = _control_eval(rows, teacher_controller)
    student_behavior = _control_eval(rows, student_controller_fn)
    teacher_e2e = _end2end_eval(rows, agent_cfg, controller_fn=None)
    student_e2e = _end2end_eval(rows, agent_cfg, controller_fn=student_controller_fn)

    task_rows = []
    key_rows = []
    key_delta = {
        "f1": 0.0,
        "avg_retrieval": 0.0,
        "avg_latency_ms": 0.0,
    }
    if args.task_breakdown:
        task_map = {r.get("id", ""): r.get("task", "unknown") for r in rows}
        task_rows.extend(_task_breakdown_from_rows("teacher_controller", teacher_e2e["rows"], task_map))
        task_rows.extend(_task_breakdown_from_rows("student_controller", student_e2e["rows"], task_map))
        key_rows.append(_key_summary(task_rows, "teacher_controller", args.key_tasks, args.key_agg))
        key_rows.append(_key_summary(task_rows, "student_controller", args.key_tasks, args.key_agg))
        teacher_key = [x for x in key_rows if x.get("model") == "teacher_controller"][0]
        student_key = [x for x in key_rows if x.get("model") == "student_controller"][0]
        key_delta = {
            "f1": student_key.get("f1", 0.0) - teacher_key.get("f1", 0.0),
            "avg_retrieval": student_key.get("avg_retrieval", 0.0) - teacher_key.get("avg_retrieval", 0.0),
            "avg_latency_ms": student_key.get("avg_latency_ms", 0.0) - teacher_key.get("avg_latency_ms", 0.0),
        }

    summary = {
        "teacher_behavior": teacher_behavior,
        "student_behavior": student_behavior,
        "teacher_e2e": {
            "f1": teacher_e2e["f1"],
            "em": teacher_e2e["em"],
            "avg_retrieval": teacher_e2e["avg_retrieval"],
            "avg_latency_ms": teacher_e2e["avg_latency_ms"],
        },
        "student_e2e": {
            "f1": student_e2e["f1"],
            "em": student_e2e["em"],
            "avg_retrieval": student_e2e["avg_retrieval"],
            "avg_latency_ms": student_e2e["avg_latency_ms"],
        },
        "delta_student_minus_teacher": {
            "f1": student_e2e["f1"] - teacher_e2e["f1"],
            "avg_retrieval": student_e2e["avg_retrieval"] - teacher_e2e["avg_retrieval"],
            "avg_latency_ms": student_e2e["avg_latency_ms"] - teacher_e2e["avg_latency_ms"],
            "trigger_acc": student_behavior["trigger_acc"] - teacher_behavior["trigger_acc"],
            "macro_f1": student_behavior["macro_f1"] - teacher_behavior["macro_f1"],
            "keyword_hit_rate": student_behavior["keyword_hit_rate"]
            - teacher_behavior["keyword_hit_rate"],
        },
        "key_task_config": {
            "enable": bool(args.task_breakdown),
            "key_tasks": list(args.key_tasks),
            "key_agg": args.key_agg,
        },
        "key_task_delta_student_minus_teacher": key_delta,
        "checkpoint_rules": rules,
    }

    write_json(Path(args.out_dir) / "student_controller_eval.json", summary)
    dump_jsonl(Path(args.out_dir) / "student_controller_teacher_rows.jsonl", teacher_e2e["rows"])
    dump_jsonl(Path(args.out_dir) / "student_controller_student_rows.jsonl", student_e2e["rows"])

    try:
        import pandas as pd
    except Exception:
        pd = None

    rows_out = [
        {
            "model": "teacher_controller",
            "f1": teacher_e2e["f1"],
            "em": teacher_e2e["em"],
            "avg_retrieval": teacher_e2e["avg_retrieval"],
            "avg_latency_ms": teacher_e2e["avg_latency_ms"],
            "trigger_acc": teacher_behavior["trigger_acc"],
            "macro_f1": teacher_behavior["macro_f1"],
            "keyword_hit_rate": teacher_behavior["keyword_hit_rate"],
            "delta_f1_vs_teacher": 0.0,
            "delta_latency_vs_teacher": 0.0,
            "delta_retrieval_vs_teacher": 0.0,
            "key_f1": key_rows[0]["f1"] if key_rows else 0.0,
            "key_avg_retrieval": key_rows[0]["avg_retrieval"] if key_rows else 0.0,
            "key_avg_latency_ms": key_rows[0]["avg_latency_ms"] if key_rows else 0.0,
            "key_delta_f1_vs_teacher": 0.0,
            "key_delta_latency_vs_teacher": 0.0,
            "key_delta_retrieval_vs_teacher": 0.0,
        },
        {
            "model": "student_controller",
            "f1": student_e2e["f1"],
            "em": student_e2e["em"],
            "avg_retrieval": student_e2e["avg_retrieval"],
            "avg_latency_ms": student_e2e["avg_latency_ms"],
            "trigger_acc": student_behavior["trigger_acc"],
            "macro_f1": student_behavior["macro_f1"],
            "keyword_hit_rate": student_behavior["keyword_hit_rate"],
            "delta_f1_vs_teacher": student_e2e["f1"] - teacher_e2e["f1"],
            "delta_latency_vs_teacher": student_e2e["avg_latency_ms"] - teacher_e2e["avg_latency_ms"],
            "delta_retrieval_vs_teacher": student_e2e["avg_retrieval"] - teacher_e2e["avg_retrieval"],
            "key_f1": key_rows[1]["f1"] if key_rows else 0.0,
            "key_avg_retrieval": key_rows[1]["avg_retrieval"] if key_rows else 0.0,
            "key_avg_latency_ms": key_rows[1]["avg_latency_ms"] if key_rows else 0.0,
            "key_delta_f1_vs_teacher": key_delta["f1"],
            "key_delta_latency_vs_teacher": key_delta["avg_latency_ms"],
            "key_delta_retrieval_vs_teacher": key_delta["avg_retrieval"],
        },
    ]

    if pd is not None:
        table = pd.DataFrame(rows_out)
        table.to_csv(Path(args.out_dir) / "student_controller_eval.csv", index=False)
    else:
        import csv

        with open(Path(args.out_dir) / "student_controller_eval.csv", "w", encoding="utf-8", newline="") as f:
            cols = list(rows_out[0].keys()) if rows_out else []
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for row in rows_out:
                w.writerow(row)

    if args.task_breakdown:
        if pd is not None:
            task_df = pd.DataFrame(task_rows)
            task_df.to_csv(Path(args.out_dir) / "student_task_metrics.csv", index=False)
            key_df = pd.DataFrame(key_rows)
            key_df.to_csv(Path(args.out_dir) / "student_key_task_summary.csv", index=False)
        else:
            import csv

            if task_rows:
                with open(
                    Path(args.out_dir) / "student_task_metrics.csv",
                    "w",
                    encoding="utf-8",
                    newline="",
                ) as f:
                    cols = list(task_rows[0].keys())
                    w = csv.DictWriter(f, fieldnames=cols)
                    w.writeheader()
                    for row in task_rows:
                        w.writerow(row)
            if key_rows:
                with open(
                    Path(args.out_dir) / "student_key_task_summary.csv",
                    "w",
                    encoding="utf-8",
                    newline="",
                ) as f:
                    cols = list(key_rows[0].keys())
                    w = csv.DictWriter(f, fieldnames=cols)
                    w.writeheader()
                    for row in key_rows:
                        w.writerow(row)

    print("student eval done -> {}".format(args.out_dir))


if __name__ == "__main__":
    main()
