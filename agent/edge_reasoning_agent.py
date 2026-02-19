import json
import re
from pathlib import Path

from agent.fact_extractor import extract_facts_from_chunks
from agent.memory import MemoryStore
from agent.prompts import (
    build_baseline_prompt,
    build_agent_prompt,
    build_repair_prompt,
    format_evidence_chunks,
    format_memory_facts,
    parse_protocol_output,
)
from utils.nvml import NvmlMonitor
from utils.timer import PhaseTimer


def _approx_tokens(text):
    text = text or ""
    if not text:
        return 0
    return max(1, len(text) // 2)


class EdgeReasoningAgent(object):
    def __init__(self, cfg, llm_driver, retrieval_index, controller_fn=None):
        self.cfg = cfg or {}
        self.llm = llm_driver
        self.index = retrieval_index
        self.controller_fn = controller_fn

    @staticmethod
    def _normalize_keyword(text):
        return " ".join(str(text or "").strip().lower().split())

    @staticmethod
    def _query_tokens(text):
        text = str(text or "").lower()
        return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", text)

    @classmethod
    def _rewrite_search_query(cls, question, keyword, max_terms=10):
        merged = []
        seen = set()
        for token in cls._query_tokens(question) + cls._query_tokens(keyword):
            if token in seen:
                continue
            seen.add(token)
            merged.append(token)
            if len(merged) >= max(1, int(max_terms)):
                break
        if merged:
            return " ".join(merged)
        return (str(keyword or "").strip() or str(question or "").strip())

    @classmethod
    def _build_forced_search_keyword(cls, question, fallback="", max_terms=8):
        merged = []
        seen = set()
        for token in cls._query_tokens(question):
            if token in seen:
                continue
            seen.add(token)
            merged.append(token)
            if len(merged) >= max(1, int(max_terms)):
                break
        if merged:
            return " ".join(merged)
        return (str(fallback or "").strip() or str(question or "").strip())

    @staticmethod
    def _clean_single_doc_answer(text):
        src = str(text or "").strip()
        if not src:
            return src, False, ""
        out = src
        notes = []

        # Remove common chain-of-thought style lead-ins.
        lead_patterns = [
            r"^\s*(wait|maybe|however|well)\b[\s,:-]*",
            r"^\s*(i think|it seems|let me|i'm not sure|not sure)\b[\s,:-]*",
            r"^\s*(answer\s*[:：]|final answer\s*[:：])\s*",
        ]
        changed = True
        while changed:
            changed = False
            for pat in lead_patterns:
                m = re.match(pat, out, flags=re.I)
                if m:
                    out = out[m.end() :].strip()
                    notes.append("strip_prefix")
                    changed = True

        # Trim obvious trailing fragments.
        tail_markers = [" which", " that", " and", " or", ",", ":", ";"]
        lower = out.lower()
        for marker in tail_markers:
            if lower.endswith(marker):
                out = out[: len(out) - len(marker)].rstrip(" ,:;")
                notes.append("trim_tail_marker")
                break

        # Keep only the first clean sentence when the output is verbose.
        if len(out) > 0:
            chunks = re.split(r"(?<=[\.\!\?。！？])\s+", out)
            if len(chunks) >= 2 and len(chunks[0]) >= 8:
                if len(out) > 220 or "wait" in src.lower():
                    out = chunks[0].strip()
                    notes.append("first_sentence")

        out = " ".join(out.split())
        applied = out != src
        note = ";".join(sorted(set(notes)))
        return out, applied, note

    @staticmethod
    def _compact_answer(text, question, max_chars=96):
        src = str(text or "").strip()
        if not src:
            return src, False, ""
        q = str(question or "").strip().lower()
        out = src
        notes = []

        # Keep the first sentence by default to reduce verbose tails.
        parts = re.split(r"(?<=[\.\!\?。！？])\s+", out)
        if len(parts) >= 2 and len(parts[0].strip()) >= 4:
            out = parts[0].strip()
            notes.append("first_sentence")

        # Extract concise spans for common QA patterns.
        span_patterns = []
        if q.startswith("where"):
            span_patterns += [r"\b(?:born|located|in)\s+in\s+([^.;,\n]+(?:,\s*[^.;,\n]+)?)"]
        if q.startswith("who"):
            span_patterns += [r"\bwas\s+([^.;,\n]+)", r"\bis\s+([^.;,\n]+)"]
        if "position" in q:
            span_patterns += [r"\bposition of\s+([^.;,\n]+)"]
        span_patterns += [r"\bwas born in\s+([^.;,\n]+(?:,\s*[^.;,\n]+)?)"]

        for pat in span_patterns:
            m = re.search(pat, src, flags=re.I)
            if m:
                candidate = (m.group(1) or "").strip(" .,:;")
                if candidate:
                    out = candidate
                    notes.append("regex_span")
                    break

        # Remove markdown emphasis and excess spaces.
        out = re.sub(r"[*_`]+", "", out)
        out = " ".join(out.split()).strip(" ,;")
        if len(out) > int(max_chars):
            out = out[: int(max_chars)].rstrip(" ,;")
            notes.append("trim_len")

        return out, (out != src), ";".join(sorted(set(notes)))

    @staticmethod
    def _is_single_doc_generic_question(question, cfg):
        cfg = cfg or {}
        if not bool(cfg.get("enable", False)):
            return False, ""
        text = str(question or "").strip().lower()
        patterns = cfg.get("patterns", []) or []
        for p in patterns:
            pat = str(p or "").strip().lower()
            if pat and pat in text:
                return True, pat
        return False, ""

    @staticmethod
    def _is_low_confidence_final(pred, question, cfg):
        cfg = cfg or {}
        text = str(pred or "").strip()
        if not text:
            return True, "empty"

        lower = text.lower()
        reasons = []
        min_answer_chars = int(cfg.get("min_answer_chars", 24))
        if len(text) < max(1, min_answer_chars):
            reasons.append("short_answer")

        uncertainty_markers = cfg.get("uncertainty_markers", []) or []
        for marker in uncertainty_markers:
            mk = str(marker or "").strip().lower()
            if mk and mk in lower:
                reasons.append("uncertainty_marker")
                break

        truncated_tail_markers = cfg.get("truncated_tail_markers", []) or []
        for marker in truncated_tail_markers:
            mk = str(marker or "").strip().lower()
            if not mk:
                continue
            if lower.endswith(mk):
                reasons.append("truncated_tail")
                break

        q = str(question or "").strip()
        if q and len(q) > 0:
            if q.lower().startswith("how many") or q.startswith("多少"):
                if re.search(r"\d", text) is None:
                    reasons.append("count_missing_number")

        return (len(reasons) > 0), ";".join(reasons)

    @staticmethod
    def _parse_protocol_relaxed(text):
        src = str(text or "").strip()
        if not src:
            return None, ""

        m = re.search(r"<\s*(final|search)\s*>(.*?)<\s*/\s*\1\s*>", src, flags=re.I | re.S)
        if m:
            return m.group(1).lower(), (m.group(2) or "").strip()

        # Handle truncated tags like "<final>..."
        for tag in ["final", "search"]:
            marker = "<{}>".format(tag)
            pos = src.lower().find(marker)
            if pos >= 0:
                content = src[pos + len(marker) :].strip()
                if content:
                    return tag, content

        # Handle malformed opening like "...search>keyword</search>"
        for tag in ["final", "search"]:
            marker = "{}>".format(tag)
            pos = src.lower().find(marker)
            if pos >= 0:
                content = src[pos + len(marker) :].strip()
                end = "</{}>".format(tag)
                end_pos = content.lower().find(end)
                if end_pos >= 0:
                    content = content[:end_pos]
                if content:
                    return tag, content.strip()

        return None, ""

    def run_sample(self, sample, trace_path=None):
        question = sample.get("question", "")
        gold = sample.get("answer", "")
        sid = sample.get("id", "")
        task = str(sample.get("task", "unknown")).strip().lower()

        agent_cfg = self.cfg.get("agent", {})
        retrieval_cfg = self.cfg.get("retrieval", {})
        model_cfg = self.cfg.get("model", {})
        model_decoding_cfg = model_cfg.get("decoding", {})
        logging_cfg = self.cfg.get("logging", {})
        answer_top_p = float(model_decoding_cfg.get("top_p", 1.0))
        answer_top_k = int(model_decoding_cfg.get("top_k", 0))

        base_max_steps = int(agent_cfg.get("max_steps", 6))
        top_k_init = int(retrieval_cfg.get("top_k_init", 3))
        top_k_iter = int(retrieval_cfg.get("top_k_iter", 1))
        memory_strategy = agent_cfg.get("memory_strategy", "fact_memory")
        max_prompt_tokens = int(agent_cfg.get("max_prompt_tokens", 8000))
        facts_per_step = int(agent_cfg.get("facts_per_step", 6))
        inject_cfg = agent_cfg.get("injection_defense", {})
        early_stop_cfg = agent_cfg.get("early_stop", {})
        format_repair_cfg = agent_cfg.get("format_repair", {})
        early_stop_enable = bool(early_stop_cfg.get("enable", False))
        max_same_keyword_hits = max(1, int(early_stop_cfg.get("max_same_keyword_hits", 2)))
        max_no_new_chunk_steps = max(1, int(early_stop_cfg.get("max_no_new_chunk_steps", 2)))
        enable_single_doc_shortcut = bool(early_stop_cfg.get("enable_single_doc_shortcut", False))
        single_doc_max_steps = max(1, int(early_stop_cfg.get("single_doc_max_steps", 2)))
        enable_query_rewrite_retry = bool(early_stop_cfg.get("enable_query_rewrite_retry", True))
        format_repair_enable = bool(format_repair_cfg.get("enable", True))
        format_repair_max_retries = max(0, int(format_repair_cfg.get("max_retries", 1)))
        protocol_decoding_cfg = agent_cfg.get("protocol_decoding", {}) or {}
        answer_postprocess_cfg = agent_cfg.get("answer_postprocess", {}) or {}
        single_doc_generic_cfg = agent_cfg.get("single_doc_generic", {}) or {}
        answer_postprocess_enable = bool(answer_postprocess_cfg.get("enable", False))
        answer_postprocess_max_chars = int(answer_postprocess_cfg.get("max_chars", 96))
        single_doc_compact_enable = bool(answer_postprocess_cfg.get("single_doc_compact", False))
        entity_compact_cfg = answer_postprocess_cfg.get("entity_compact", {}) or {}
        entity_compact_enable = bool(entity_compact_cfg.get("enable", False))
        task_overrides = agent_cfg.get("task_overrides", {})
        single_doc_override = {}
        code_override = {}
        multi_doc_override = {}
        task_override = {}
        if isinstance(task_overrides, dict):
            single_doc_override = task_overrides.get("single_doc_qa", {}) or {}
            code_override = task_overrides.get("code_qa", {}) or {}
            multi_doc_override = task_overrides.get("multi_doc_qa", {}) or {}
            task_override = task_overrides.get(task, {}) or {}
        single_doc_top_k_init = int(single_doc_override.get("top_k_init", 3))
        enable_single_doc_final_refine = bool(single_doc_override.get("enable_final_refine", False))
        single_doc_refine_max_new_tokens = int(
            single_doc_override.get("final_refine_max_new_tokens", 192)
        )
        single_doc_refine_temperature = float(
            single_doc_override.get("final_refine_temperature", 0.2)
        )
        single_doc_always_refine = bool(single_doc_override.get("always_refine", False))
        decoding_budget_cfg = agent_cfg.get("decoding_budget", {}) or {}
        decoding_budget_enable = bool(decoding_budget_cfg.get("enable", False))
        short_question_token_threshold = int(
            decoding_budget_cfg.get("short_question_token_threshold", 12)
        )
        short_question_max_new_tokens = int(
            decoding_budget_cfg.get("short_question_max_new_tokens", 192)
        )
        budget_default_max_new_tokens = decoding_budget_cfg.get("default_max_new_tokens")
        budget_task_caps = decoding_budget_cfg.get("task_caps", {}) or {}
        default_temperature = float(model_decoding_cfg.get("temperature", 0.2))
        single_doc_temperature = single_doc_override.get("temperature")
        effective_temperature = default_temperature
        if task == "single_doc_qa" and single_doc_temperature is not None:
            effective_temperature = float(single_doc_temperature)
        if isinstance(task_override, dict) and task_override.get("temperature") is not None:
            effective_temperature = float(task_override.get("temperature"))
        default_max_new_tokens = int(model_decoding_cfg.get("max_new_tokens", 256))
        single_doc_max_new_tokens = single_doc_override.get("max_new_tokens")
        effective_max_new_tokens = default_max_new_tokens
        if task == "single_doc_qa" and single_doc_max_new_tokens is not None:
            effective_max_new_tokens = int(single_doc_max_new_tokens)
        if isinstance(task_override, dict) and task_override.get("max_new_tokens") is not None:
            effective_max_new_tokens = int(task_override.get("max_new_tokens"))
        effective_max_new_tokens_pre_budget = int(effective_max_new_tokens)
        query_token_count = len(self._query_tokens(question))
        short_question_budget_applied = False
        if decoding_budget_enable:
            if budget_default_max_new_tokens is not None:
                effective_max_new_tokens = min(
                    effective_max_new_tokens, int(budget_default_max_new_tokens)
                )
            if isinstance(budget_task_caps, dict) and budget_task_caps.get(task) is not None:
                effective_max_new_tokens = min(
                    effective_max_new_tokens, int(budget_task_caps.get(task))
                )
            if query_token_count <= max(1, short_question_token_threshold):
                effective_max_new_tokens = min(
                    effective_max_new_tokens, max(32, short_question_max_new_tokens)
                )
                short_question_budget_applied = True
        effective_top_k_init = top_k_init
        effective_top_k_iter = top_k_iter
        effective_max_steps = base_max_steps
        effective_enable_single_doc_shortcut = enable_single_doc_shortcut
        if isinstance(task_override, dict):
            if task_override.get("top_k_init") is not None:
                effective_top_k_init = max(effective_top_k_init, int(task_override.get("top_k_init")))
            if task_override.get("top_k_iter") is not None:
                effective_top_k_iter = max(1, int(task_override.get("top_k_iter")))
            if task_override.get("max_steps") is not None:
                effective_max_steps = max(effective_max_steps, int(task_override.get("max_steps")))

        task_low_conf_cfg = {}
        task_low_conf_enable = False
        if isinstance(task_override, dict):
            task_low_conf_cfg = task_override.get("low_confidence", {}) or {}
            task_low_conf_enable = bool(task_low_conf_cfg.get("enable", False))

        task_forced_retrieve_cfg = {}
        task_forced_retrieve_enable = False
        task_forced_retrieve_max_extra = 0
        task_forced_retrieve_top_k_extra = 1
        task_force_on_first_final = False
        if isinstance(task_override, dict):
            task_forced_retrieve_cfg = task_override.get("forced_retrieve", {}) or {}
            task_forced_retrieve_enable = bool(task_forced_retrieve_cfg.get("enable", False))
            task_forced_retrieve_max_extra = max(
                0, int(task_forced_retrieve_cfg.get("max_extra_searches", 1))
            )
            task_forced_retrieve_top_k_extra = max(
                1, int(task_forced_retrieve_cfg.get("top_k_extra", 1))
            )
            task_force_on_first_final = bool(
                task_forced_retrieve_cfg.get("force_on_first_final", False)
            )

        long_context_cfg = single_doc_override.get("long_context", {}) or {}
        long_context_enable = bool(long_context_cfg.get("enable", False))
        long_context_threshold_chars = int(long_context_cfg.get("threshold_chars", 80000))
        long_context_top_k_init = int(long_context_cfg.get("top_k_init", 4))
        long_context_max_steps = int(long_context_cfg.get("max_steps", 4))
        long_context_shortcut = bool(
            long_context_cfg.get("enable_single_doc_shortcut", False)
        )
        long_context_disable_refine = bool(
            long_context_cfg.get("disable_refine_over_threshold", False)
        )
        long_context_disable_forced_retrieve = bool(
            long_context_cfg.get("disable_forced_retrieve_over_threshold", False)
        )
        task_enable_query_rewrite_retry = bool(enable_query_rewrite_retry)
        task_rewrite_requires_no_new = False
        if task == "multi_doc_qa" and isinstance(multi_doc_override, dict):
            if multi_doc_override.get("enable_query_rewrite_retry") is not None:
                task_enable_query_rewrite_retry = bool(
                    multi_doc_override.get("enable_query_rewrite_retry")
                )
            task_rewrite_requires_no_new = bool(
                multi_doc_override.get("rewrite_requires_no_new_chunks", True)
            )
        single_doc_generic_applied = False
        single_doc_generic_pattern = ""
        if task == "single_doc_qa":
            single_doc_generic_applied, single_doc_generic_pattern = self._is_single_doc_generic_question(
                question, single_doc_generic_cfg
            )
            if single_doc_generic_applied:
                generic_max_steps = int(single_doc_generic_cfg.get("max_steps", 2))
                effective_max_steps = min(effective_max_steps, max(1, generic_max_steps))
                if bool(single_doc_generic_cfg.get("disable_refine", True)):
                    enable_single_doc_final_refine = False
                task_forced_retrieve_enable = False

        context_chars = int(
            sum([len((d or {}).get("text", "")) for d in sample.get("documents", [])])
        )
        long_context_applied = False

        if task == "single_doc_qa":
            effective_top_k_init = max(top_k_init, single_doc_top_k_init)
            if long_context_enable and context_chars >= long_context_threshold_chars:
                long_context_applied = True
                effective_top_k_init = max(effective_top_k_init, long_context_top_k_init)
                effective_max_steps = max(effective_max_steps, long_context_max_steps)
                effective_enable_single_doc_shortcut = long_context_shortcut
                if long_context_disable_forced_retrieve:
                    task_forced_retrieve_enable = False
                if long_context_disable_refine:
                    enable_single_doc_final_refine = False

        budget_profile = {
            "query_token_count": int(query_token_count),
            "short_question_budget_applied": bool(short_question_budget_applied),
            "pre_budget_max_new_tokens": int(effective_max_new_tokens_pre_budget),
            "post_budget_max_new_tokens": int(effective_max_new_tokens),
            "default_budget_cap": int(budget_default_max_new_tokens)
            if budget_default_max_new_tokens is not None
            else 0,
            "task_budget_cap": int(budget_task_caps.get(task))
            if isinstance(budget_task_caps, dict) and budget_task_caps.get(task) is not None
            else 0,
        }

        protocol_temperature = float(
            protocol_decoding_cfg.get("temperature", effective_temperature)
        )
        protocol_top_p = float(protocol_decoding_cfg.get("top_p", answer_top_p))
        protocol_top_k = int(protocol_decoding_cfg.get("top_k", answer_top_k))
        protocol_max_new_tokens = int(
            protocol_decoding_cfg.get("max_new_tokens", effective_max_new_tokens)
        )

        timer = PhaseTimer()
        monitor = NvmlMonitor(sample_ms=logging_cfg.get("nvml_sample_ms", 200))

        memory = MemoryStore(strategy=memory_strategy, max_prompt_tokens=max_prompt_tokens)
        trace = {
            "id": sid,
            "question": question,
            "steps": [],
            "effective_top_k_init": int(effective_top_k_init),
            "effective_top_k_iter": int(effective_top_k_iter),
            "effective_max_steps": int(effective_max_steps),
            "effective_temperature": float(effective_temperature),
            "effective_max_new_tokens": int(effective_max_new_tokens),
            "effective_max_new_tokens_pre_budget": int(effective_max_new_tokens_pre_budget),
            "protocol_temperature": float(protocol_temperature),
            "protocol_top_p": float(protocol_top_p),
            "protocol_top_k": int(protocol_top_k),
            "protocol_max_new_tokens": int(protocol_max_new_tokens),
            "decoding_budget_enabled": bool(decoding_budget_enable),
            "context_chars": int(context_chars),
            "long_context_applied": bool(long_context_applied),
            "single_doc_generic_applied": bool(single_doc_generic_applied),
            "single_doc_generic_pattern": single_doc_generic_pattern,
            "budget_profile": budget_profile,
        }

        with timer.phase("retrieval"):
            init_hits = self.index.search(question, top_k=effective_top_k_init)
        memory.add_chunks(init_hits)
        memory.prune_to_budget()

        n_retrieval = 1 if init_hits else 0
        retrieved_chunks_total = len(init_hits)
        prompt_tokens_total = 0
        completion_tokens_total = 0
        error_count = 0
        pred = ""
        last_search_keyword = ""
        same_keyword_hits = 0
        no_new_chunk_steps = 0
        rewrite_used = False

        forced_search_count = 0

        for step in range(1, effective_max_steps + 1):
            monitor.sample()
            with timer.phase("overhead"):
                dropped = memory.prune_to_budget()

            evidence_text = format_evidence_chunks(memory.chunks, injection_cfg=inject_cfg)
            facts_text = ""
            if memory_strategy == "fact_memory":
                facts_text = format_memory_facts(memory.facts, max_items=facts_per_step)
            prompt = build_agent_prompt(
                question=question,
                evidence_text=evidence_text,
                step=step,
                max_steps=effective_max_steps,
                memory_strategy=memory_strategy,
                facts_text=facts_text,
                note="budget_tokens={}".format(memory.token_count()),
            )
            prompt_tokens_total += _approx_tokens(prompt)

            if self.controller_fn is not None:
                with timer.phase("llm"):
                    raw = self.controller_fn(
                        question=question,
                        evidence=evidence_text,
                        step=step,
                        max_steps=effective_max_steps,
                        sample=sample,
                    )
            else:
                with timer.phase("llm"):
                    raw = self.llm.generate(
                        prompt,
                        expect_protocol=True,
                        temperature=protocol_temperature,
                        top_p=protocol_top_p,
                        top_k=protocol_top_k,
                        max_new_tokens=protocol_max_new_tokens,
                    )
            completion_tokens_total += _approx_tokens(raw)
            tag, content = parse_protocol_output(raw)
            if tag is None:
                tag, content = self._parse_protocol_relaxed(raw)

            repaired = False
            repair_attempts = 0
            last_repair_output = ""
            format_repair_failed = False
            if tag is None and format_repair_enable:
                repaired = True
                repair_input = raw
                while tag is None and repair_attempts < format_repair_max_retries:
                    repair_prompt = build_repair_prompt(
                        raw_output=repair_input, question=question, evidence_text=evidence_text
                    )
                    prompt_tokens_total += _approx_tokens(repair_prompt)
                    with timer.phase("llm"):
                        repaired_raw = self.llm.generate(
                            repair_prompt,
                            expect_protocol=True,
                            temperature=protocol_temperature,
                            top_p=protocol_top_p,
                            top_k=protocol_top_k,
                            max_new_tokens=protocol_max_new_tokens,
                        )
                    completion_tokens_total += _approx_tokens(repaired_raw)
                    repair_attempts += 1
                    last_repair_output = repaired_raw
                    tag, content = parse_protocol_output(repaired_raw)
                    if tag is None:
                        tag, content = self._parse_protocol_relaxed(repaired_raw)
                    repair_input = repaired_raw

            if tag is None:
                format_repair_failed = True
                tag = "final"
                content = memory.best_answer_from_chunks(question)
                error_count += 1

            step_info = {
                "step": step,
                "raw_output": raw,
                "parsed_tag": tag,
                "parsed_content": content,
                "repaired": repaired,
                "repair_attempts": int(repair_attempts),
                "last_repair_output": last_repair_output,
                "format_repair_failed": bool(format_repair_failed),
                "dropped": dropped,
                "rewrite_used": False,
                "rewrite_keyword": "",
                "rewrite_hits": [],
                "rewrite_new_chunk_ids": [],
                "low_confidence_detected": False,
                "low_confidence_reason": "",
                "forced_search_applied": False,
                "forced_search_keyword": "",
                "forced_search_hits": [],
                "forced_search_new_chunk_ids": [],
                "forced_final": False,
                "early_stop_reason": "",
            }

            if tag == "search":
                keyword = content.strip() or question
                normalized_keyword = self._normalize_keyword(keyword)
                if normalized_keyword and normalized_keyword == last_search_keyword:
                    same_keyword_hits += 1
                else:
                    same_keyword_hits = 1
                last_search_keyword = normalized_keyword

                before_chunk_ids = set([c.get("chunk_id", "") for c in memory.chunks])
                with timer.phase("retrieval"):
                    hits = self.index.search(keyword, top_k=effective_top_k_iter)
                n_retrieval += 1
                retrieved_chunks_total += len(hits)
                memory.add_chunks(hits)
                new_chunk_ids = []
                for h in hits:
                    cid = h.get("chunk_id", "")
                    if cid and cid not in before_chunk_ids:
                        new_chunk_ids.append(cid)
                if new_chunk_ids:
                    no_new_chunk_steps = 0
                else:
                    no_new_chunk_steps += 1

                facts = extract_facts_from_chunks(hits, limit=facts_per_step)
                memory.add_facts(facts)
                dropped_after = memory.prune_to_budget()
                step_info["search_keyword"] = keyword
                step_info["retrieval_hits"] = [h.get("chunk_id", "") for h in hits]
                step_info["new_chunk_ids"] = new_chunk_ids
                step_info["same_keyword_hits"] = int(same_keyword_hits)
                step_info["no_new_chunk_steps"] = int(no_new_chunk_steps)
                step_info["facts"] = facts
                step_info["dropped_after"] = dropped_after

                early_stop_reasons = []
                if early_stop_enable:
                    if same_keyword_hits >= max_same_keyword_hits:
                        early_stop_reasons.append(
                            "same_keyword_hits>={}".format(max_same_keyword_hits)
                        )
                    if no_new_chunk_steps >= max_no_new_chunk_steps:
                        early_stop_reasons.append(
                            "no_new_chunk_steps>={}".format(max_no_new_chunk_steps)
                        )
                    if (
                        effective_enable_single_doc_shortcut
                        and task == "single_doc_qa"
                        and step >= single_doc_max_steps
                    ):
                        early_stop_reasons.append(
                            "single_doc_shortcut_step>={}".format(single_doc_max_steps)
                        )

                if early_stop_reasons:
                    rewrite_triggered = bool(
                        (same_keyword_hits >= max_same_keyword_hits)
                        or (no_new_chunk_steps >= max_no_new_chunk_steps)
                    )
                    if task == "multi_doc_qa" and task_rewrite_requires_no_new:
                        rewrite_triggered = bool(
                            no_new_chunk_steps >= max_no_new_chunk_steps
                        )
                    if (
                        early_stop_enable
                        and task_enable_query_rewrite_retry
                        and rewrite_triggered
                        and (not rewrite_used)
                    ):
                        rewrite_keyword = self._rewrite_search_query(question, keyword)
                        normalized_rewrite = self._normalize_keyword(rewrite_keyword)
                        if normalized_rewrite and normalized_rewrite != normalized_keyword:
                            rewrite_used = True
                            step_info["rewrite_used"] = True
                            step_info["rewrite_keyword"] = rewrite_keyword
                            before_rewrite_chunk_ids = set([c.get("chunk_id", "") for c in memory.chunks])
                            with timer.phase("retrieval"):
                                rewrite_hits = self.index.search(
                                    rewrite_keyword, top_k=effective_top_k_iter
                                )
                            n_retrieval += 1
                            retrieved_chunks_total += len(rewrite_hits)
                            memory.add_chunks(rewrite_hits)
                            rewrite_new_chunk_ids = []
                            for h in rewrite_hits:
                                cid = h.get("chunk_id", "")
                                if cid and cid not in before_rewrite_chunk_ids:
                                    rewrite_new_chunk_ids.append(cid)
                            if rewrite_new_chunk_ids:
                                no_new_chunk_steps = 0
                            else:
                                no_new_chunk_steps += 1
                            if normalized_rewrite == last_search_keyword:
                                same_keyword_hits += 1
                            else:
                                same_keyword_hits = 1
                            last_search_keyword = normalized_rewrite

                            rewrite_facts = extract_facts_from_chunks(rewrite_hits, limit=facts_per_step)
                            memory.add_facts(rewrite_facts)
                            rewrite_dropped_after = memory.prune_to_budget()
                            step_info["rewrite_hits"] = [h.get("chunk_id", "") for h in rewrite_hits]
                            step_info["rewrite_new_chunk_ids"] = rewrite_new_chunk_ids
                            step_info["rewrite_dropped_after"] = rewrite_dropped_after
                            step_info["same_keyword_hits"] = int(same_keyword_hits)
                            step_info["no_new_chunk_steps"] = int(no_new_chunk_steps)

                            early_stop_reasons = []
                            if same_keyword_hits >= max_same_keyword_hits:
                                early_stop_reasons.append(
                                    "same_keyword_hits>={}".format(max_same_keyword_hits)
                                )
                            if no_new_chunk_steps >= max_no_new_chunk_steps:
                                early_stop_reasons.append(
                                    "no_new_chunk_steps>={}".format(max_no_new_chunk_steps)
                                )
                            if (
                                effective_enable_single_doc_shortcut
                                and task == "single_doc_qa"
                                and step >= single_doc_max_steps
                            ):
                                early_stop_reasons.append(
                                    "single_doc_shortcut_step>={}".format(single_doc_max_steps)
                                )

                    if early_stop_reasons:
                        pred = memory.best_answer_from_chunks(question)
                        step_info["forced_final"] = True
                        step_info["early_stop_reason"] = ";".join(early_stop_reasons)
                        trace["steps"].append(step_info)
                        break

                trace["steps"].append(step_info)
                continue

            pred_candidate = content.strip() or memory.best_answer_from_chunks(question)
            low_confidence_detected = False
            low_confidence_reason = ""
            if task_low_conf_enable:
                low_confidence_detected, low_confidence_reason = self._is_low_confidence_final(
                    pred_candidate,
                    question,
                    task_low_conf_cfg,
                )
            step_info["low_confidence_detected"] = bool(low_confidence_detected)
            step_info["low_confidence_reason"] = low_confidence_reason

            force_retrieve_hit = bool(low_confidence_detected or task_force_on_first_final)
            if (
                tag == "final"
                and step == 1
                and task_forced_retrieve_enable
                and force_retrieve_hit
                and forced_search_count < task_forced_retrieve_max_extra
            ):
                forced_search_count += 1
                forced_keyword = self._build_forced_search_keyword(question, fallback=pred_candidate)
                before_chunk_ids = set([c.get("chunk_id", "") for c in memory.chunks])
                with timer.phase("retrieval"):
                    forced_hits = self.index.search(
                        forced_keyword, top_k=task_forced_retrieve_top_k_extra
                    )
                n_retrieval += 1
                retrieved_chunks_total += len(forced_hits)
                memory.add_chunks(forced_hits)
                forced_new_chunk_ids = []
                for h in forced_hits:
                    cid = h.get("chunk_id", "")
                    if cid and cid not in before_chunk_ids:
                        forced_new_chunk_ids.append(cid)
                if forced_new_chunk_ids:
                    no_new_chunk_steps = 0
                else:
                    no_new_chunk_steps += 1
                forced_facts = extract_facts_from_chunks(forced_hits, limit=facts_per_step)
                memory.add_facts(forced_facts)
                forced_dropped_after = memory.prune_to_budget()
                step_info["forced_search_applied"] = True
                step_info["forced_search_keyword"] = forced_keyword
                step_info["forced_search_hits"] = [h.get("chunk_id", "") for h in forced_hits]
                step_info["forced_search_new_chunk_ids"] = forced_new_chunk_ids
                step_info["forced_search_dropped_after"] = forced_dropped_after
                trace["steps"].append(step_info)
                continue

            pred = pred_candidate
            trace["steps"].append(step_info)
            break

        if not pred:
            pred = memory.best_answer_from_chunks(question)

        postprocess_applied = False
        postprocess_note = ""
        if task == "single_doc_qa":
            pred, postprocess_applied, postprocess_note = self._clean_single_doc_answer(pred)
            if answer_postprocess_enable and single_doc_compact_enable:
                compact_pred, compact_applied, compact_note = self._compact_answer(
                    pred,
                    question,
                    max_chars=answer_postprocess_max_chars,
                )
                if compact_applied:
                    pred = compact_pred
                    postprocess_applied = True
                    if postprocess_note:
                        postprocess_note = "{};{}".format(postprocess_note, compact_note)
                    else:
                        postprocess_note = compact_note
        if (
            task in ("multi_doc_qa", "code_qa")
            and answer_postprocess_enable
            and entity_compact_enable
        ):
            compact_pred, compact_applied, compact_note = self._compact_answer(
                pred,
                question,
                max_chars=answer_postprocess_max_chars,
            )
            if compact_applied:
                pred = compact_pred
                if postprocess_note:
                    postprocess_note = "{};{}".format(postprocess_note, compact_note)
                else:
                    postprocess_note = compact_note
                postprocess_applied = True

        single_doc_refined = False
        single_doc_refine_reason = ""
        refine_triggered = False
        refine_skip_reason = ""
        if task == "single_doc_qa" and not enable_single_doc_final_refine:
            if long_context_applied and long_context_disable_refine:
                refine_skip_reason = "long_context_guard"
            else:
                refine_skip_reason = "disabled_by_config"
        if task == "single_doc_qa" and enable_single_doc_final_refine and trace.get("steps"):
            last_step = trace["steps"][-1] or {}
            pred_text = (pred or "").strip()
            low_confidence = (
                bool(single_doc_always_refine)
                or
                bool(last_step.get("format_repair_failed"))
                or bool(last_step.get("low_confidence_detected"))
                or bool(last_step.get("forced_final"))
                or len(pred_text) < 24
            )
            if low_confidence:
                reason_parts = []
                if single_doc_always_refine:
                    reason_parts.append("always_refine")
                if last_step.get("forced_final"):
                    reason_parts.append("forced_final")
                if last_step.get("format_repair_failed"):
                    reason_parts.append("format_repair_failed")
                if last_step.get("low_confidence_detected"):
                    reason_parts.append(
                        "low_confidence:{}".format(last_step.get("low_confidence_reason", ""))
                    )
                if len(pred_text) < 24:
                    reason_parts.append("short_pred")
                if not reason_parts:
                    reason_parts.append("low_confidence")

                refine_evidence = format_evidence_chunks(memory.chunks, injection_cfg=inject_cfg)
                refine_prompt = build_baseline_prompt(question, refine_evidence)
                refine_triggered = True
                prompt_tokens_total += _approx_tokens(refine_prompt)
                with timer.phase("llm"):
                    refined_pred = self.llm.generate(
                        refine_prompt,
                        expect_protocol=False,
                        temperature=single_doc_refine_temperature,
                        top_p=answer_top_p,
                        top_k=answer_top_k,
                        max_new_tokens=single_doc_refine_max_new_tokens,
                    )
                completion_tokens_total += _approx_tokens(refined_pred)
                if (refined_pred or "").strip():
                    pred = refined_pred.strip()
                    pred, refined_post_applied, refined_post_note = self._clean_single_doc_answer(pred)
                    if refined_post_applied:
                        postprocess_applied = True
                        if postprocess_note:
                            postprocess_note = "{};{}".format(postprocess_note, refined_post_note)
                        else:
                            postprocess_note = refined_post_note
                    single_doc_refined = True
                single_doc_refine_reason = ";".join(reason_parts)
            else:
                refine_skip_reason = "low_confidence_gate_not_met"

        trace["single_doc_refined"] = bool(single_doc_refined)
        trace["single_doc_refine_reason"] = single_doc_refine_reason
        trace["refine_triggered"] = bool(refine_triggered)
        trace["refine_skip_reason"] = refine_skip_reason
        trace["postprocess_applied"] = bool(postprocess_applied)
        trace["postprocess_note"] = postprocess_note

        monitor.sample()
        latency = timer.summary()
        gpu_mem = monitor.summary()
        monitor.close()

        last_step = trace["steps"][-1] if trace.get("steps") else {}
        low_confidence_detected_any = any(
            [bool(s.get("low_confidence_detected", False)) for s in trace.get("steps", [])]
        )
        forced_search_applied_any = any(
            [bool(s.get("forced_search_applied", False)) for s in trace.get("steps", [])]
        )
        forced_search_keywords = []
        for s in trace.get("steps", []):
            kw = str(s.get("forced_search_keyword", "") or "").strip()
            if kw and kw not in forced_search_keywords:
                forced_search_keywords.append(kw)

        result = {
            "id": sid,
            "pred": pred,
            "gold": gold,
            "n_steps": max(1, len(trace["steps"])),
            "n_retrieval": int(n_retrieval),
            "latency_ms": {
                "total": float(latency.get("total", 0.0)),
                "llm": float(latency.get("llm", 0.0)),
                "retrieval": float(latency.get("retrieval", 0.0)),
                "overhead": float(latency.get("overhead", 0.0)),
            },
            "gpu_mem_mb": gpu_mem,
            "pruning_log": memory.pruning_log,
            "error_count": int(error_count),
            "prompt_tokens_total": int(prompt_tokens_total),
            "completion_tokens_total": int(completion_tokens_total),
            "retrieved_chunks_total": int(retrieved_chunks_total),
            "backend_mode": getattr(self.llm, "backend_mode", "unknown"),
            "single_doc_refined": bool(single_doc_refined),
            "single_doc_refine_reason": single_doc_refine_reason,
            "refine_triggered": bool(refine_triggered),
            "refine_skip_reason": refine_skip_reason,
            "low_confidence_detected": bool(low_confidence_detected_any),
            "low_confidence_reason": last_step.get("low_confidence_reason", ""),
            "forced_search_applied": bool(forced_search_applied_any),
            "forced_search_keyword": "|".join(forced_search_keywords),
            "postprocess_applied": bool(postprocess_applied),
            "postprocess_note": postprocess_note,
            "budget_profile": budget_profile,
        }

        if trace_path:
            path = Path(trace_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")

        return result, trace
