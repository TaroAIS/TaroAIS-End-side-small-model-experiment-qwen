#!/usr/bin/env python3
import argparse
from pathlib import Path

from agent.prompts import build_baseline_prompt, format_evidence_chunks
from llm.driver_hf import HFLLMDriver
from llm.driver_local import LocalLLMDriver
from retrieval.index_faiss import RetrievalIndex, build_and_save_index
from utils.io import dump_jsonl, load_jsonl, load_yaml
from utils.metadata import snapshot_configs, write_run_metadata
from utils.nvml import NvmlMonitor
from utils.runtime import create_run_dir, detect_hardware, project_root, schema_path
from utils.schema import validate_records
from utils.timer import PhaseTimer


def _build_driver(cfg):
    backend = cfg.get("model", {}).get("backend", "local")
    if backend == "hf":
        return HFLLMDriver(cfg)
    return LocalLLMDriver(cfg)


def _load_or_build_index(cfg, dataset_rows, index_dir):
    if index_dir and (Path(index_dir) / "index_meta.json").exists():
        try:
            return RetrievalIndex.load(index_dir)
        except Exception:
            pass

    retrieval_cfg = cfg.get("retrieval", {})
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
    )
    return idx


def main():
    parser = argparse.ArgumentParser(description="Run baseline RAG and write prediction JSONL.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--index_dir", default="data/index")
    args = parser.parse_args()

    cfg = load_yaml(args.config)
    rows = load_jsonl(args.dataset)
    validate_records(rows, schema_path("dataset.schema.json"), context_prefix="dataset")

    driver = _build_driver(cfg)
    index = _load_or_build_index(cfg, rows, args.index_dir)
    top_k = int(cfg.get("retrieval", {}).get("top_k", 5))

    results = []
    for sample in rows:
        sid = sample.get("id", "")
        q = sample.get("question", "")
        gold = sample.get("answer", "")

        monitor = NvmlMonitor(sample_ms=cfg.get("logging", {}).get("nvml_sample_ms", 200))
        timer = PhaseTimer()

        with timer.phase("retrieval"):
            hits = index.search(q, top_k=top_k)
        context = format_evidence_chunks(hits, injection_cfg={"enable": False, "quote_chunks": False, "label_as_evidence": False})

        prompt = build_baseline_prompt(q, context)
        with timer.phase("llm"):
            pred = driver.generate(prompt, expect_protocol=False)

        monitor.sample()
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
            "error_count": 0,
        }
        monitor.close()
        results.append(result)

    validate_records(results, schema_path("result.schema.json"), context_prefix="result")
    dump_jsonl(args.out, results)

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
    write_run_metadata(
        run_dir=run_dir,
        schema_path=schema_path("run_metadata.schema.json"),
        config_paths=[args.config],
        model_info=model_info,
        hardware=detect_hardware(),
        seed=42,
        repo_dir=project_root().parent,
    )

    print("baseline done: {} samples -> {}".format(len(results), args.out))


if __name__ == "__main__":
    main()
