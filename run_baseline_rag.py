#!/usr/bin/env python3
import argparse
from pathlib import Path

from agent.prompts import build_baseline_prompt, format_evidence_chunks
from llm.driver_hf import HFLLMDriver
from llm.driver_local import LocalLLMDriver
from retrieval.chunking import build_chunks_from_documents
from retrieval.index_faiss import RetrievalIndex, build_and_save_index
from utils.io import append_jsonl, dump_jsonl, load_jsonl, load_yaml
from utils.metadata import snapshot_configs, write_run_metadata
from utils.nvml import NvmlMonitor
from utils.runtime import create_run_dir, detect_hardware, project_root, schema_path
from utils.schema import validate_records
from utils.timer import PhaseTimer


def _approx_tokens(text):
    text = text or ""
    if not text:
        return 0
    return max(1, len(text) // 2)


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
        "baseline resume: existing_results={} remaining_samples={} out={}".format(
            len(filtered_existing), len(remaining), out_path
        ),
        flush=True,
    )
    return filtered_existing, remaining


def main():
    parser = argparse.ArgumentParser(description="Run baseline RAG and write prediction JSONL.")
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
    cfg["runtime"] = {"run_mode": args.run_mode, "seed": int(args.seed)}

    rows = load_jsonl(args.dataset)
    validate_records(rows, schema_path("dataset.schema.json"), context_prefix="dataset")
    rows, start_idx, end_idx, total_rows = _slice_rows(rows, args.start_idx, args.end_idx)
    slice_rows = rows

    driver = _build_driver(cfg)
    top_k = int(cfg.get("retrieval", {}).get("top_k", 5))
    retrieval_cfg = cfg.get("retrieval", {})
    runtime_mode = str(args.run_mode).lower()

    global_index = None
    if args.retrieval_scope == "global":
        global_index = _load_or_build_index(cfg, slice_rows, args.index_dir)

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

    if completed_count == total_target:
        print(
            "baseline resume already complete: {} samples [{}:{}) of {} -> {}".format(
                total_target, start_idx, end_idx, total_rows, args.out
            ),
            flush=True,
        )

    buffer = []
    for done_count, sample in enumerate(rows_to_run, start=completed_count + 1):
        sid = sample.get("id", "")
        q = sample.get("question", "")
        gold = sample.get("answer", "")

        monitor = NvmlMonitor(sample_ms=cfg.get("logging", {}).get("nvml_sample_ms", 200))
        timer = PhaseTimer()

        sample_index = global_index
        if args.retrieval_scope == "sample":
            sample_index = _build_sample_index(sample, retrieval_cfg, runtime_mode)

        with timer.phase("retrieval"):
            hits = sample_index.search(q, top_k=top_k)
        context = format_evidence_chunks(
            hits,
            injection_cfg={"enable": False, "quote_chunks": False, "label_as_evidence": False},
        )

        prompt = build_baseline_prompt(q, context)
        sample_error = 0
        backend_mode = "real"
        with timer.phase("llm"):
            try:
                pred = driver.generate(prompt, expect_protocol=False)
                backend_mode = getattr(driver, "backend_mode", "unknown")
            except Exception:
                # Keep formal run alive for statistical aggregation when backend has sporadic timeouts.
                sample_error = 1
                pred = ((hits[0] or {}).get("text", "") if hits else "")[:160]
                backend_mode = "unknown"

        monitor.sample()
        if args.run_mode == "formal" and backend_mode != "real" and sample_error == 0:
            raise RuntimeError(
                "Formal mode requires real backend output, got backend_mode={}".format(backend_mode)
            )

        result = {
            "id": sid,
            "pred": (pred or "").strip(),
            "gold": gold,
            "n_steps": 1,
            "n_retrieval": 1 if hits else 0,
            "latency_ms": {
                "total": float(timer.summary().get("total", 0.0)),
                "llm": float(timer.summary().get("llm", 0.0)),
                "retrieval": float(timer.summary().get("retrieval", 0.0)),
            },
            "gpu_mem_mb": monitor.summary(),
            "error_count": int(sample_error),
            "backend_mode": backend_mode,
            "prompt_tokens_total": int(_approx_tokens(prompt)),
            "completion_tokens_total": int(_approx_tokens(pred)),
            "retrieved_chunks_total": int(len(hits)),
        }
        monitor.close()
        buffer.append(result)

        if len(buffer) >= flush_every:
            append_jsonl(args.out, buffer)
            buffer = []

        if done_count % progress_interval == 0 or done_count == total_target:
            print(
                "baseline progress: {} / {} slice [{}:{}) -> {}".format(
                    done_count, total_target, start_idx, end_idx, args.out
                ),
                flush=True,
            )

    if buffer:
        append_jsonl(args.out, buffer)

    if not Path(args.out).exists():
        dump_jsonl(args.out, existing_results)

    final_results = load_jsonl(args.out)
    validate_records(final_results, result_schema, context_prefix="result")
    if len(final_results) != total_target:
        raise RuntimeError(
            "Incomplete baseline output: expected {} rows, got {} rows for {}".format(
                total_target, len(final_results), args.out
            )
        )

    run_dir = create_run_dir(base_dir="results")
    snapshot_configs([args.config], run_dir / "config_snapshot")

    model_cfg = cfg.get("model", {})
    model_info = {
        "backend": model_cfg.get("backend", "local"),
        "name_or_path": model_cfg.get("name_or_path", "unknown"),
        "quantization": model_cfg.get("quantization", "unknown"),
        "n_ctx": int(model_cfg.get("n_ctx", 8192)),
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
        "baseline done: {} samples [{}:{}) of {} -> {}".format(
            len(final_results), start_idx, end_idx, total_rows, args.out
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
