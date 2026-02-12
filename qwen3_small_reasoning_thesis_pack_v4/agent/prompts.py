import re


def _strip_injection(text, patterns):
    out = text
    for p in patterns or []:
        out = out.replace(p, "")
    return out


def format_evidence_chunks(chunks, injection_cfg=None):
    injection_cfg = injection_cfg or {}
    enable = bool(injection_cfg.get("enable", False))
    strip_patterns = injection_cfg.get("strip_patterns", [])
    quote_chunks = bool(injection_cfg.get("quote_chunks", True))
    label = bool(injection_cfg.get("label_as_evidence", True))

    lines = []
    for c in chunks:
        txt = c.get("text", "")
        if enable:
            txt = _strip_injection(txt, strip_patterns)
        doc_id = c.get("doc_id", "")
        chunk_id = c.get("chunk_id", "")
        head = ""
        if label:
            head = "【Evidence】{}#{}: ".format(doc_id, chunk_id)
        body = txt.strip()
        if quote_chunks:
            body = "```\n{}\n```".format(body)
        lines.append(head + body)
    return "\n".join(lines)


def build_baseline_prompt(question, context):
    return (
        "你是一个严谨的问答助手。请只根据 Context 回答 Question，答案要简洁。\n"
        "Question: {}\n"
        "Context:\n{}\n"
        "请输出最终答案，不要输出推理过程。"
    ).format(question, context)


def build_agent_prompt(question, evidence_text, step, max_steps, memory_strategy, note=""):
    return (
        "你是端侧检索推理代理。你必须严格按协议输出：\n"
        "- 信息不足：<search>关键词</search>\n"
        "- 信息足够：<final>答案</final>\n"
        "不要输出其他文本。\n\n"
        "[STEP]\n{}\n[/STEP]\n"
        "[MAX_STEPS]\n{}\n[/MAX_STEPS]\n"
        "[MEMORY_STRATEGY]\n{}\n[/MEMORY_STRATEGY]\n"
        "[QUESTION]\n{}\n[/QUESTION]\n"
        "[EVIDENCE]\n{}\n[/EVIDENCE]\n"
        "[NOTE]\n{}\n[/NOTE]\n"
    ).format(step, max_steps, memory_strategy, question, evidence_text, note)


def build_repair_prompt(raw_output, question, evidence_text):
    return (
        "你上次输出不符合协议。仅允许以下两种格式之一：\n"
        "<search>关键词</search> 或 <final>答案</final>。\n"
        "不要输出任何其他文本。\n\n"
        "[REPAIR_OUTPUT]\n{}\n[/REPAIR_OUTPUT]\n"
        "[QUESTION]\n{}\n[/QUESTION]\n"
        "[EVIDENCE]\n{}\n[/EVIDENCE]\n"
    ).format(raw_output, question, evidence_text)


def parse_protocol_output(text):
    text = (text or "").strip()
    m_final = re.search(r"<final>(.*?)</final>", text, flags=re.S | re.I)
    if m_final:
        return "final", m_final.group(1).strip()
    m_search = re.search(r"<search>(.*?)</search>", text, flags=re.S | re.I)
    if m_search:
        return "search", m_search.group(1).strip()
    return None, ""
