import json
from pathlib import Path

from agent.fact_extractor import extract_facts_from_chunks
from agent.memory import MemoryStore
from agent.prompts import (
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

    def run_sample(self, sample, trace_path=None):
        question = sample.get("question", "")
        gold = sample.get("answer", "")
        sid = sample.get("id", "")
        task = str(sample.get("task", "unknown")).strip().lower()

        agent_cfg = self.cfg.get("agent", {})
        retrieval_cfg = self.cfg.get("retrieval", {})
        logging_cfg = self.cfg.get("logging", {})

        max_steps = int(agent_cfg.get("max_steps", 6))
        top_k_init = int(retrieval_cfg.get("top_k_init", 3))
        top_k_iter = int(retrieval_cfg.get("top_k_iter", 1))
        memory_strategy = agent_cfg.get("memory_strategy", "fact_memory")
        max_prompt_tokens = int(agent_cfg.get("max_prompt_tokens", 8000))
        facts_per_step = int(agent_cfg.get("facts_per_step", 6))
        inject_cfg = agent_cfg.get("injection_defense", {})
        early_stop_cfg = agent_cfg.get("early_stop", {})
        early_stop_enable = bool(early_stop_cfg.get("enable", False))
        max_same_keyword_hits = max(1, int(early_stop_cfg.get("max_same_keyword_hits", 2)))
        max_no_new_chunk_steps = max(1, int(early_stop_cfg.get("max_no_new_chunk_steps", 2)))
        enable_single_doc_shortcut = bool(early_stop_cfg.get("enable_single_doc_shortcut", False))
        single_doc_max_steps = max(1, int(early_stop_cfg.get("single_doc_max_steps", 2)))

        timer = PhaseTimer()
        monitor = NvmlMonitor(sample_ms=logging_cfg.get("nvml_sample_ms", 200))

        memory = MemoryStore(strategy=memory_strategy, max_prompt_tokens=max_prompt_tokens)
        trace = {
            "id": sid,
            "question": question,
            "steps": [],
        }

        with timer.phase("retrieval"):
            init_hits = self.index.search(question, top_k=top_k_init)
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

        for step in range(1, max_steps + 1):
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
                max_steps=max_steps,
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
                        max_steps=max_steps,
                        sample=sample,
                    )
            else:
                with timer.phase("llm"):
                    raw = self.llm.generate(prompt, expect_protocol=True)
            completion_tokens_total += _approx_tokens(raw)
            tag, content = parse_protocol_output(raw)

            repaired = False
            if tag is None:
                repaired = True
                repair_prompt = build_repair_prompt(
                    raw_output=raw, question=question, evidence_text=evidence_text
                )
                prompt_tokens_total += _approx_tokens(repair_prompt)
                with timer.phase("llm"):
                    repaired_raw = self.llm.generate(repair_prompt, expect_protocol=True)
                completion_tokens_total += _approx_tokens(repaired_raw)
                tag, content = parse_protocol_output(repaired_raw)
                if tag is None:
                    tag = "final"
                    content = memory.best_answer_from_chunks(question)
                    error_count += 1

            step_info = {
                "step": step,
                "raw_output": raw,
                "parsed_tag": tag,
                "parsed_content": content,
                "repaired": repaired,
                "dropped": dropped,
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
                    hits = self.index.search(keyword, top_k=top_k_iter)
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
                        enable_single_doc_shortcut
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

            pred = content.strip() or memory.best_answer_from_chunks(question)
            trace["steps"].append(step_info)
            break

        if not pred:
            pred = memory.best_answer_from_chunks(question)

        monitor.sample()
        latency = timer.summary()
        gpu_mem = monitor.summary()
        monitor.close()

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
        }

        if trace_path:
            path = Path(trace_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")

        return result, trace
