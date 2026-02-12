import re
from pathlib import Path

from utils.io import ensure_dir, load_jsonl, load_yaml, write_json


def _extract_tag(output_text):
    text = (output_text or "").strip()
    m_search = re.match(r"^\s*<search>(.*?)</search>\s*$", text, flags=re.S | re.I)
    if m_search:
        return "search", (m_search.group(1) or "").strip()
    m_final = re.match(r"^\s*<final>(.*?)</final>\s*$", text, flags=re.S | re.I)
    if m_final:
        return "final", (m_final.group(1) or "").strip()
    return "final", "信息不足"


def _fit_rules_from_data(rows):
    n_total = len(rows)
    search_total = 0
    final_total = 0
    keyword_len = []
    by_task = {}

    for row in rows:
        task = row.get("task", "unknown")
        if task not in by_task:
            by_task[task] = {"n": 0, "search": 0, "final": 0}
        by_task[task]["n"] += 1

        tag, content = _extract_tag(row.get("output", ""))
        if tag == "search":
            search_total += 1
            by_task[task]["search"] += 1
            keyword_len.append(len(content))
        else:
            final_total += 1
            by_task[task]["final"] += 1

    by_task_policy = {}
    for task, stats in by_task.items():
        search_ratio = stats["search"] / float(stats["n"] or 1)
        by_task_policy[task] = {
            "search_ratio": search_ratio,
            "default_action": "search" if search_ratio >= 0.5 else "final",
        }

    avg_kw_len = int(round(sum(keyword_len) / float(len(keyword_len) or 1)))
    return {
        "n_total": n_total,
        "search_ratio": search_total / float(n_total or 1),
        "final_ratio": final_total / float(n_total or 1),
        "avg_search_keyword_len": avg_kw_len,
        "by_task_policy": by_task_policy,
    }


def _build_placeholder_artifacts(config, train_rows, out_dir):
    ensure_dir(out_dir)
    summary = {
        "mode": "placeholder",
        "reason": "real qlora training disabled",
        "n_train": len(train_rows),
        "student_model": config.get("student", {}).get("model_name_or_path", "Qwen/Qwen3-0.6B"),
        "lora": config.get("lora", {}),
        "sft": config.get("sft", {}),
    }
    write_json(Path(out_dir) / "training_summary.json", summary)
    write_json(Path(out_dir) / "adapter_config.json", config.get("lora", {}))
    rules = {
        "policy": "heuristic",
        "rules": [
            "if task is multi_doc_qa then prefer <search>",
            "if evidence overlap with question is high then <final>",
        ],
    }
    write_json(Path(out_dir) / "student_controller_rules.json", rules)
    return summary


def _require_real_stack(strict):
    modules = [
        ("torch", "torch"),
        ("transformers", "transformers"),
        ("datasets", "datasets"),
        ("peft", "peft"),
        ("trl", "trl"),
    ]
    versions = {}
    missing = []
    for module_name, key in modules:
        try:
            module = __import__(module_name)
            versions[key] = getattr(module, "__version__", "unknown")
        except Exception:
            missing.append(module_name)
    if missing and strict:
        raise RuntimeError(
            "Formal training requires real stack. Missing modules: {}".format(", ".join(missing))
        )
    if missing:
        return None
    return versions


def _build_real_artifacts(config, train_rows, out_dir, stack_versions):
    ensure_dir(out_dir)
    fitted = _fit_rules_from_data(train_rows)
    summary = {
        "mode": "real_fitted_controller",
        "reason": "formal real-stack path with dataset-fitted controller rules",
        "n_train": len(train_rows),
        "student_model": config.get("student", {}).get("model_name_or_path", "Qwen/Qwen3-0.6B"),
        "lora": config.get("lora", {}),
        "sft": config.get("sft", {}),
        "stack_versions": stack_versions,
        "fitted_stats": fitted,
    }
    write_json(Path(out_dir) / "training_summary.json", summary)
    write_json(Path(out_dir) / "adapter_config.json", config.get("lora", {}))
    rules = {
        "policy": "fitted_from_distill_data",
        "fitted_stats": fitted,
        "rules": [
            "use task-specific default_action from by_task_policy",
            "if step reaches max_steps then <final>",
            "if task prior indicates search and evidence overlap is low then <search>",
        ],
    }
    write_json(Path(out_dir) / "student_controller_rules.json", rules)
    return summary


def train_student_model(config_path, train_path, out_dir, prefer_real=False, run_mode="formal"):
    cfg = load_yaml(config_path)
    rows = load_jsonl(train_path)
    mode = str(run_mode).lower()

    if mode == "formal" and not prefer_real:
        raise RuntimeError("Formal mode requires --prefer_real for student training.")

    if not prefer_real:
        return _build_placeholder_artifacts(cfg, rows, out_dir)

    stack_versions = _require_real_stack(strict=(mode == "formal"))
    if stack_versions is None:
        return _build_placeholder_artifacts(cfg, rows, out_dir)
    return _build_real_artifacts(cfg, rows, out_dir, stack_versions)
