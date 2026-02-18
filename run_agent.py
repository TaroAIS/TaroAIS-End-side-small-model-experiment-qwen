#!/usr/bin/env python3
import argparse
from pathlib import Path

from agent.edge_reasoning_agent import EdgeReasoningAgent
from llm.driver_hf import HFLLMDriver
from llm.driver_local import LocalLLMDriver
from retrieval.chunking import build_chunks_from_documents
from retrieval.index_faiss import RetrievalIndex, build_and_save_index
from utils.io import dump_jsonl, load_jsonl, load_yaml
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


def main():
    parser = argparse.ArgumentParser(description="Run edge reasoning agent and write prediction JSONL.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--index_dir", default="data/index")
    parser.add_argument("--run_mode", choices=["smoke", "formal"], default="formal")
    parser.add_argument("--retrieval_scope", choices=["sample", "global"], default="sample")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    cfg = load_yaml(args.config)
    cfg = dict(cfg)
    cfg["runtime"] = {"run_mode": args.run_mode, "seed": int(args.seed)}

    rows = load_jsonl(args.dataset)
    validate_records(rows, schema_path("dataset.schema.json"), context_prefix="dataset")

    driver = _build_driver(cfg)

    global_index = None
    if args.retrieval_scope == "global":
        global_index = _load_or_build_index(cfg, rows, args.index_dir)

    run_dir = create_run_dir(base_dir="results")
    trace_dir = Path(run_dir) / "trace"
    save_trace = bool(cfg.get("logging", {}).get("save_trace", True))
    retrieval_cfg = cfg.get("retrieval", {})
    runtime_mode = str(args.run_mode).lower()

    results = []
    for sample in rows:
        if args.retrieval_scope == "sample":
            idx = _build_sample_index(sample, retrieval_cfg, runtime_mode)
        else:
            idx = global_index
        agent = EdgeReasoningAgent(cfg=cfg, llm_driver=driver, retrieval_index=idx)

        trace_path = None
        if save_trace:
            trace_path = trace_dir / "{}.json".format(sample.get("id", "sample"))
        result, _trace = agent.run_sample(sample, trace_path=trace_path)
        if "backend_mode" not in result:
            result["backend_mode"] = getattr(driver, "backend_mode", "unknown")
        if args.run_mode == "formal" and result.get("backend_mode") != "real":
            raise RuntimeError(
                "Formal mode requires real backend output, got backend_mode={}".format(
                    result.get("backend_mode")
                )
            )
        results.append(result)

    validate_records(results, schema_path("result.schema.json"), context_prefix="result")
    dump_jsonl(args.out, results)

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

    print("agent done: {} samples -> {}".format(len(results), args.out))


if __name__ == "__main__":
    main()
