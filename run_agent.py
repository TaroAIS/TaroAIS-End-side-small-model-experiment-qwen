#!/usr/bin/env python3
import argparse
import json
import multiprocessing as mp
import time
from pathlib import Path

from agent.edge_reasoning_agent import EdgeReasoningAgent
from agent.memory import MemoryStore
from llm.driver_hf import HFLLMDriver
from llm.driver_local import LocalLLMDriver
from retrieval.chunking import build_chunks_from_documents
from retrieval.index_faiss import RetrievalIndex, build_and_save_index
from utils.io import append_jsonl, dump_jsonl, load_jsonl, load_yaml
from utils.metadata import snapshot_configs, write_run_metadata
from utils.runtime import create_run_dir, detect_hardware, project_root, schema_path
from utils.schema import validate_records


def _build_driver(cfg):
    backend = cfg.get("model", {}).get("backend", "local")
    if backend == "hf":
        return HFLLMDriver(cfg)
    return LocalLLMDriver(cfg)


def _load_or_build_index(cfg, dataset_rows, index_dir):
    retrieval_cfg = cfg.get("retrieval", {})
    runtime_mode = str(cfg.get("runtime", {}).get("run_mode", "formal")).lower()
    require_dense_in_formal = bool(retrieval_cfg.get("require_dense_in_formal", False))
    hybrid_cfg = retrieval_cfg.get("hybrid", {})

    if index_dir and (Path(index_dir) / "index_meta.json").exists():
        try:
            idx = RetrievalIndex.load(index_dir)
            if require_dense_in_formal and runtime_mode == "formal" and idx.mode == "lexical":
                raise RuntimeError(
                    "Formal mode requires dense retrieval, but loaded index is lexical: {}".format(
                        index_dir
                    )
                )
            return idx
        except Exception:
            pass

    chunk_size = int(retrieval_cfg.get("chunk_size", 512))
    chunk_overlap = int(retrieval_cfg.get("chunk_overlap", 128))
    emb_model = retrieval_cfg.get("embedding_model", "sentence-transformers")
    index_type = retrieval_cfg.get("index", "faiss")

    if index_dir:
        out_chunk = str(Path(index_dir) / "chunks.jsonl")
    else:
        index_dir = str(project_root() / "data" / "runtime_index")
        out_chunk = str(Path(index_dir) / "chunks.jsonl")

    _, idx = build_and_save_index(
        dataset_rows=dataset_rows,
        out_chunk_path=out_chunk,
        index_dir=index_dir,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        embedding_model=emb_model,
        index_type=index_type,
        hybrid_cfg=hybrid_cfg,
        runtime_mode=runtime_mode,
        require_dense_in_formal=require_dense_in_formal,
    )
    return idx


def _build_sample_index(sample, retrieval_cfg, runtime_mode):
    chunk_size = int(retrieval_cfg.get("chunk_size", 512))
    chunk_overlap = int(retrieval_cfg.get("chunk_overlap", 128))
    emb_model = retrieval_cfg.get("embedding_model", "sentence-transformers")
    index_type = retrieval_cfg.get("sample_index", "lexical")
    hybrid_cfg = retrieval_cfg.get("hybrid", {})
    require_dense_in_formal = bool(retrieval_cfg.get("require_dense_in_formal", False))
    docs = sample.get("documents", [])
    chunks = build_chunks_from_documents(
        docs,
        sample_id=sample.get("id", "sample"),
        chunk_size=chunk_size,
        overlap=chunk_overlap,
    )
    idx = RetrievalIndex(
        embedding_model=emb_model,
        index_type=index_type,
        hybrid_cfg=hybrid_cfg,
        runtime_mode=runtime_mode,
        require_dense_in_formal=require_dense_in_formal,
    )
    idx.build(chunks)
    return idx


def _slice_rows(rows, start_idx, end_idx):
    total = len(rows)
    start = max(0, int(start_idx))
    end = total if end_idx is None else min(total, int(end_idx))
    if end < start:
        raise ValueError("end_idx must be >= start_idx")
    return rows[start:end], start, end, total


def _prepare_resume(out_path, rows, schema_file, resume_enabled):
    out_file = Path(out_path)
    if not resume_enabled:
        if out_file.exists():
            out_file.unlink()
        return [], rows

    if not out_file.exists():
        return [], rows

    existing = load_jsonl(out_path)
    if not existing:
        return [], rows

    validate_records(existing, schema_file, context_prefix="result_resume")

    slice_ids = {sample.get("id") for sample in rows}
    seen = set()
    filtered_existing = []
    for row in existing:
        sid = row.get("id")
        if sid not in slice_ids:
            continue
        if sid in seen:
            raise RuntimeError("Duplicate resume result id: {}".format(sid))
        seen.add(sid)
        filtered_existing.append(row)

    remaining = [sample for sample in rows if sample.get("id") not in seen]
    print(
        "agent resume: existing_results={} remaining_samples={} out={}".format(
            len(filtered_existing), len(remaining), out_path
        ),
        flush=True,
    )
    return filtered_existing, remaining


def _default_sample_timeout_s(cfg):
    runtime_cfg = cfg.get("runtime", {}) or {}
    if runtime_cfg.get("sample_timeout_s") is not None:
        return max(0, int(runtime_cfg.get("sample_timeout_s")))
    local_cfg = cfg.get("local_backend", {}) or {}
    if local_cfg.get("hard_timeout_s") is not None:
        return max(0, int(local_cfg.get("hard_timeout_s")))
    request_timeout_s = int(local_cfg.get("request_timeout_s", 120))
    return max(600, request_timeout_s * 3)


def _sample_doc_chars(sample):
    total = 0
    for doc in sample.get("documents", []) or []:
        total += len((doc or {}).get("text", "") or "")
    return int(total)


def _build_timeout_fallback_result(sample, cfg, elapsed_s, reason, stage):
    retrieval_cfg = cfg.get("retrieval", {}) or {}
    agent_cfg = cfg.get("agent", {}) or {}
    task = str(sample.get("task", "unknown") or "unknown").strip().lower()
    question = str(sample.get("question", "") or "")
    gold = str(sample.get("answer", "") or "")
    docs = sample.get("documents", []) or []
    chunk_size = int(retrieval_cfg.get("chunk_size", 512))
    chunk_overlap = int(retrieval_cfg.get("chunk_overlap", 128))
    top_k = max(1, int(retrieval_cfg.get("top_k_init", 2)))
    chunks = build_chunks_from_documents(
        docs,
        sample_id=sample.get("id", "sample"),
        chunk_size=chunk_size,
        overlap=chunk_overlap,
    )

    q_tokens = set(EdgeReasoningAgent._query_tokens(question))
    ranked = []
    for chunk in chunks:
        text = str((chunk or {}).get("text", "") or "")
        lower = text.lower()
        overlap = 0
        for token in q_tokens:
            if token in lower:
                overlap += 1
        scored = dict(chunk)
        scored["score"] = float(overlap)
        ranked.append(scored)
    ranked.sort(key=lambda x: (float(x.get("score", 0.0)), len(str(x.get("text", "") or ""))), reverse=True)
    top_chunks = ranked[:top_k]

    answer_type = "open_text"
    if task == "single_doc_qa":
        task_overrides = agent_cfg.get("task_overrides", {}) or {}
        single_doc_override = task_overrides.get("single_doc_qa", {}) or {}
        answer_type = EdgeReasoningAgent._single_doc_answer_type(
            question, single_doc_override.get("answer_type_policy", {}) or {}
        )

    memory = MemoryStore(
        strategy=agent_cfg.get("memory_strategy", "fact_memory"),
        max_prompt_tokens=int(agent_cfg.get("max_prompt_tokens", 8000)),
    )
    memory.add_chunks(top_chunks)
    pred = memory.best_answer_from_chunks(
        question,
        task=task,
        answer_type=answer_type,
        max_chars=64 if task == "single_doc_qa" else 96,
    )

    return {
        "id": sample.get("id", ""),
        "pred": str(pred or "").strip(),
        "gold": gold,
        "n_steps": 1,
        "n_retrieval": 1 if top_chunks else 0,
        "latency_ms": {
            "total": float(max(0.0, elapsed_s) * 1000.0),
            "llm": 0.0,
            "retrieval": 0.0,
            "overhead": float(max(0.0, elapsed_s) * 1000.0),
        },
        "gpu_mem_mb": {"peak": 0.0, "mean": 0.0, "series": []},
        "pruning_log": memory.pruning_log,
        "error_count": 1,
        "prompt_tokens_total": 0,
        "completion_tokens_total": 0,
        "retrieved_chunks_total": int(len(top_chunks)),
        "backend_mode": "unknown",
        "answer_type": answer_type,
        "timeout_fallback": True,
        "timeout_stage": str(stage or ""),
        "timeout_reason": str(reason or ""),
        "doc_chars": int(_sample_doc_chars(sample)),
    }


def _write_timeout_trace(trace_path, sample, elapsed_s, reason, stage):
    if not trace_path:
        return
    payload = {
        "id": sample.get("id", ""),
        "question": sample.get("question", ""),
        "timeout_fallback": True,
        "timeout_stage": str(stage or ""),
        "timeout_reason": str(reason or ""),
        "elapsed_s": float(max(0.0, elapsed_s)),
        "doc_chars": int(_sample_doc_chars(sample)),
        "steps": [],
    }
    path = Path(trace_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sample_worker_loop(cfg, runtime_mode, conn):
    retrieval_cfg = cfg.get("retrieval", {}) or {}
    driver = _build_driver(cfg)
    try:
        while True:
            msg = conn.recv()
            cmd = msg.get("cmd")
            if cmd == "stop":
                break
            if cmd != "run_sample":
                continue
            sample = msg.get("sample") or {}
            trace_path = msg.get("trace_path")
            try:
                idx = _build_sample_index(sample, retrieval_cfg, runtime_mode)
                agent = EdgeReasoningAgent(cfg=cfg, llm_driver=driver, retrieval_index=idx)
                result, _trace = agent.run_sample(sample, trace_path=trace_path)
                conn.send({"ok": True, "result": result})
            except Exception as exc:
                conn.send({"ok": False, "error": repr(exc)})
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _spawn_sample_worker(cfg, runtime_mode):
    ctx = mp.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe()
    proc = ctx.Process(
        target=_sample_worker_loop,
        args=(cfg, runtime_mode, child_conn),
        daemon=True,
    )
    proc.start()
    child_conn.close()
    return proc, parent_conn


def _stop_sample_worker(proc, conn):
    try:
        if conn is not None:
            try:
                if proc is not None and proc.is_alive():
                    conn.send({"cmd": "stop"})
            except Exception:
                pass
            conn.close()
    except Exception:
        pass
    try:
        if proc is not None and proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)
    except Exception:
        pass


def _run_sample_via_worker(proc, conn, sample, trace_path, timeout_s):
    if proc is None or (not proc.is_alive()):
        raise RuntimeError("sample worker is not alive")
    conn.send({"cmd": "run_sample", "sample": sample, "trace_path": trace_path})
    if conn.poll(timeout_s):
        return conn.recv()
    return {"ok": False, "timed_out": True}


def main():
    parser = argparse.ArgumentParser(description="Run edge reasoning agent and write prediction JSONL.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--index_dir", default="data/index")
    parser.add_argument("--run_mode", choices=["smoke", "formal"], default="formal")
    parser.add_argument("--retrieval_scope", choices=["sample", "global"], default="sample")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start_idx", type=int, default=0)
    parser.add_argument("--end_idx", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--flush_every", type=int, default=1)
    parser.add_argument("--progress_interval", type=int, default=10)
    args = parser.parse_args()

    cfg = load_yaml(args.config)
    cfg = dict(cfg)
    runtime_cfg = dict(cfg.get("runtime", {}) or {})
    runtime_cfg["run_mode"] = args.run_mode
    runtime_cfg["seed"] = int(args.seed)
    cfg["runtime"] = runtime_cfg

    rows = load_jsonl(args.dataset)
    validate_records(rows, schema_path("dataset.schema.json"), context_prefix="dataset")
    rows, start_idx, end_idx, total_rows = _slice_rows(rows, args.start_idx, args.end_idx)
    slice_rows = rows

    driver = _build_driver(cfg)

    global_index = None
    if args.retrieval_scope == "global":
        global_index = _load_or_build_index(cfg, slice_rows, args.index_dir)

    run_dir = create_run_dir(base_dir="results")
    trace_dir = Path(run_dir) / "trace"
    save_trace = bool(cfg.get("logging", {}).get("save_trace", True))
    retrieval_cfg = cfg.get("retrieval", {})
    runtime_mode = str(args.run_mode).lower()
    result_schema = schema_path("result.schema.json")

    existing_results, rows_to_run = _prepare_resume(
        out_path=args.out,
        rows=slice_rows,
        schema_file=result_schema,
        resume_enabled=bool(args.resume),
    )
    completed_count = len(existing_results)
    total_target = len(slice_rows)
    flush_every = max(1, int(args.flush_every))
    progress_interval = max(1, int(args.progress_interval))
    sample_timeout_s = _default_sample_timeout_s(cfg)
    use_sample_worker = bool(sample_timeout_s > 0 and args.retrieval_scope == "sample")
    sample_worker = None
    sample_conn = None
    if use_sample_worker:
        sample_worker, sample_conn = _spawn_sample_worker(cfg=cfg, runtime_mode=runtime_mode)
        print(
            "agent sample worker enabled: timeout_s={} run_mode={} retrieval_scope={}".format(
                sample_timeout_s, runtime_mode, args.retrieval_scope
            ),
            flush=True,
        )

    if completed_count == total_target:
        print(
            "agent resume already complete: {} samples [{}:{}) of {} -> {}".format(
                total_target, start_idx, end_idx, total_rows, args.out
            ),
            flush=True,
        )

    buffer = []
    try:
        for done_count, sample in enumerate(rows_to_run, start=completed_count + 1):
            sample_id = sample.get("id", "sample")
            doc_chars = _sample_doc_chars(sample)
            print(
                "agent sample start: {} doc_chars={} task={} timeout_s={}".format(
                    sample_id, doc_chars, sample.get("task", "unknown"), sample_timeout_s
                ),
                flush=True,
            )
            sample_started_at = time.perf_counter()
            trace_path = None
            if save_trace:
                trace_path = trace_dir / "{}.json".format(sample_id)

            status_note = "ok"
            try:
                if use_sample_worker:
                    if sample_worker is None or (not sample_worker.is_alive()):
                        _stop_sample_worker(sample_worker, sample_conn)
                        sample_worker, sample_conn = _spawn_sample_worker(
                            cfg=cfg, runtime_mode=runtime_mode
                        )
                    worker_resp = _run_sample_via_worker(
                        proc=sample_worker,
                        conn=sample_conn,
                        sample=sample,
                        trace_path=str(trace_path) if trace_path else None,
                        timeout_s=sample_timeout_s,
                    )
                    elapsed_s = time.perf_counter() - sample_started_at
                    if worker_resp.get("timed_out"):
                        status_note = "sample_timeout"
                        _stop_sample_worker(sample_worker, sample_conn)
                        sample_worker, sample_conn = _spawn_sample_worker(
                            cfg=cfg, runtime_mode=runtime_mode
                        )
                        result = _build_timeout_fallback_result(
                            sample=sample,
                            cfg=cfg,
                            elapsed_s=elapsed_s,
                            reason="sample worker timeout after {}s".format(sample_timeout_s),
                            stage="sample_worker_timeout",
                        )
                        _write_timeout_trace(
                            trace_path=trace_path,
                            sample=sample,
                            elapsed_s=elapsed_s,
                            reason=result.get("timeout_reason", ""),
                            stage=result.get("timeout_stage", ""),
                        )
                    elif not worker_resp.get("ok", False):
                        status_note = "sample_worker_error"
                        _stop_sample_worker(sample_worker, sample_conn)
                        sample_worker, sample_conn = _spawn_sample_worker(
                            cfg=cfg, runtime_mode=runtime_mode
                        )
                        result = _build_timeout_fallback_result(
                            sample=sample,
                            cfg=cfg,
                            elapsed_s=elapsed_s,
                            reason=str(worker_resp.get("error", "worker error")),
                            stage="sample_worker_error",
                        )
                        _write_timeout_trace(
                            trace_path=trace_path,
                            sample=sample,
                            elapsed_s=elapsed_s,
                            reason=result.get("timeout_reason", ""),
                            stage=result.get("timeout_stage", ""),
                        )
                    else:
                        result = worker_resp["result"]
                else:
                    if args.retrieval_scope == "sample":
                        idx = _build_sample_index(sample, retrieval_cfg, runtime_mode)
                    else:
                        idx = global_index
                    agent = EdgeReasoningAgent(cfg=cfg, llm_driver=driver, retrieval_index=idx)
                    result, _trace = agent.run_sample(sample, trace_path=trace_path)
            except Exception as exc:
                elapsed_s = time.perf_counter() - sample_started_at
                status_note = "sample_exception"
                result = _build_timeout_fallback_result(
                    sample=sample,
                    cfg=cfg,
                    elapsed_s=elapsed_s,
                    reason=str(exc),
                    stage="sample_exception",
                )
                _write_timeout_trace(
                    trace_path=trace_path,
                    sample=sample,
                    elapsed_s=elapsed_s,
                    reason=result.get("timeout_reason", ""),
                    stage=result.get("timeout_stage", ""),
                )

            if "backend_mode" not in result:
                result["backend_mode"] = getattr(driver, "backend_mode", "unknown")
            if (
                args.run_mode == "formal"
                and result.get("backend_mode") != "real"
                and int(result.get("error_count", 0)) == 0
            ):
                raise RuntimeError(
                    "Formal mode requires real backend output, got backend_mode={}".format(
                        result.get("backend_mode")
                    )
                )
            buffer.append(result)

            sample_elapsed_s = time.perf_counter() - sample_started_at
            print(
                "agent sample done: {} elapsed_s={:.2f} backend={} errors={} steps={} status={}".format(
                    sample_id,
                    sample_elapsed_s,
                    result.get("backend_mode", "unknown"),
                    int(result.get("error_count", 0)),
                    int(result.get("n_steps", 1)),
                    status_note,
                ),
                flush=True,
            )

            if len(buffer) >= flush_every:
                append_jsonl(args.out, buffer)
                buffer = []

            if done_count % progress_interval == 0 or done_count == total_target:
                print(
                    "agent progress: {} / {} slice [{}:{}) -> {}".format(
                        done_count, total_target, start_idx, end_idx, args.out
                    ),
                    flush=True,
                )
    finally:
        _stop_sample_worker(sample_worker, sample_conn)

    if buffer:
        append_jsonl(args.out, buffer)

    if not Path(args.out).exists():
        dump_jsonl(args.out, existing_results)

    final_results = load_jsonl(args.out)
    validate_records(final_results, result_schema, context_prefix="result")
    if len(final_results) != total_target:
        raise RuntimeError(
            "Incomplete agent output: expected {} rows, got {} rows for {}".format(
                total_target, len(final_results), args.out
            )
        )

    snapshot_configs([args.config], run_dir / "config_snapshot")

    model_cfg = cfg.get("model", {})
    model_info = {
        "backend": model_cfg.get("backend", "local"),
        "name_or_path": model_cfg.get("name_or_path", "unknown"),
        "quantization": model_cfg.get("quantization", "unknown"),
        "n_ctx": int(model_cfg.get("n_ctx", cfg.get("agent", {}).get("max_prompt_tokens", 8192))),
        "n_gpu_layers": int(model_cfg.get("n_gpu_layers", 0)),
    }
    source_meta_path = project_root() / "data" / "minilongbench_source.json"
    dataset_source_meta_path = ""
    if source_meta_path.exists():
        dataset_source_meta_path = str(source_meta_path)
    write_run_metadata(
        run_dir=run_dir,
        schema_path=schema_path("run_metadata.schema.json"),
        config_paths=[args.config],
        model_info=model_info,
        hardware=detect_hardware(),
        seed=int(args.seed),
        repo_dir=project_root(),
        run_mode=args.run_mode,
        dataset_source_meta_path=dataset_source_meta_path,
    )

    print(
        "agent done: {} samples [{}:{}) of {} -> {}".format(
            len(final_results), start_idx, end_idx, total_rows, args.out
        ),
        flush=True,
    )


if __name__ == "__main__":
    mp.freeze_support()
    main()
