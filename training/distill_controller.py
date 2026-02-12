import re

from agent.prompts import parse_protocol_output


def _quality_check(tag, content, quality_cfg):
    strict = bool(quality_cfg.get("require_strict_tags", True))
    min_len = int(quality_cfg.get("min_keyword_len", 2))
    max_len = int(quality_cfg.get("max_keyword_len", 24))

    if tag not in ("search", "final"):
        return False, "invalid_tag"

    if tag == "search":
        c = (content or "").strip()
        if len(c) < min_len or len(c) > max_len:
            return False, "keyword_length"

    if strict:
        if "\n" in (content or ""):
            # strict mode keeps single-line control outputs
            content = (content or "").replace("\n", " ").strip()

    return True, "ok"


def _repair_output(raw_output, question, driver):
    prompt = (
        "请把下面输出纠正为唯一合法格式：<search>关键词</search> 或 <final>答案</final>。"
        "不要输出其他文本。\n"
        "Question: {}\n"
        "Raw: {}\n"
    ).format(question, raw_output)
    return driver.generate(prompt, expect_protocol=True)


def _evidence_summary(docs, max_docs=2, max_chars=180):
    if not docs:
        return ""
    lines = []
    for d in docs[: max(1, int(max_docs))]:
        doc_id = d.get("doc_id", "")
        text = (d.get("text", "") or "").strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        lines.append("[{}] {}".format(doc_id, text))
    return "\n".join(lines)


def distill_controller_dataset(dataset_rows, teacher_cfg, driver):
    distill_cfg = teacher_cfg.get("distill", {})
    quality_cfg = distill_cfg.get("quality", {})

    allow_repair = bool(quality_cfg.get("allow_repair_once", True))
    drop_invalid = bool(quality_cfg.get("drop_if_still_invalid", True))
    system_prompt = distill_cfg.get("system_prompt", "")

    out_rows = []
    n_invalid = 0
    n_repaired = 0
    n_dropped = 0
    search_count = 0
    final_count = 0
    task_distribution = {}

    for sample in dataset_rows:
        sid = sample.get("id", "")
        question = sample.get("question", "")
        docs = sample.get("documents", [])
        context = "\n".join([d.get("text", "") for d in docs])

        prompt = (
            "{}\n"
            "[QUESTION]\n{}\n[/QUESTION]\n"
            "[EVIDENCE]\n{}\n[/EVIDENCE]\n"
            "请严格按协议输出。"
        ).format(system_prompt, question, context)

        raw = driver.generate(prompt, expect_protocol=True)
        tag, content = parse_protocol_output(raw)
        ok, reason = _quality_check(tag, content, quality_cfg)

        repaired = False
        if not ok:
            n_invalid += 1
            if allow_repair:
                repaired = True
                fixed = _repair_output(raw, question, driver)
                tag, content = parse_protocol_output(fixed)
                ok, reason = _quality_check(tag, content, quality_cfg)
                if ok:
                    n_repaired += 1

        if not ok and drop_invalid:
            n_dropped += 1
            continue

        if tag is None:
            tag = "final"
            content = "信息不足"

        if tag == "search":
            search_count += 1
        if tag == "final":
            final_count += 1

        task = sample.get("task", "unknown")
        task_distribution[task] = int(task_distribution.get(task, 0)) + 1

        output = "<{}>{}</{}>".format(tag, content.strip(), tag)
        evidence_summary = _evidence_summary(docs)
        train_row = {
            "id": sid,
            "task": task,
            "question": question,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "Question:\n{}\n\nEvidenceSummary:\n{}".format(question, evidence_summary),
                },
            ],
            "output": output,
            "meta": {
                "repaired": repaired,
                "quality_reason": reason,
            },
        }
        out_rows.append(train_row)

    total = float(len(dataset_rows)) if dataset_rows else 1.0
    stats = {
        "total": len(dataset_rows),
        "valid": len(out_rows),
        "invalid_rate": n_invalid / total,
        "repaired_rate": n_repaired / total,
        "dropped_rate": n_dropped / total,
        "search_ratio": search_count / float(len(out_rows) or 1),
        "final_ratio": final_count / float(len(out_rows) or 1),
        "task_distribution": task_distribution,
    }
    return out_rows, stats
