#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from retrieval.index_faiss import build_and_save_index
from utils.io import load_jsonl
from utils.schema import validate_records
from utils.runtime import schema_path


def main():
    parser = argparse.ArgumentParser(description="Build retrieval corpus chunks and index.")
    parser.add_argument("--in", dest="input_path", required=True, help="Input dataset JSONL path.")
    parser.add_argument("--out", dest="out_chunk", required=True, help="Output chunk JSONL path.")
    parser.add_argument("--index_dir", required=True, help="Index directory.")
    parser.add_argument("--chunk_size", type=int, default=512)
    parser.add_argument("--chunk_overlap", type=int, default=128)
    parser.add_argument("--embedding_model", default="sentence-transformers")
    parser.add_argument("--index", default="faiss", help="faiss|numpy|lexical")
    args = parser.parse_args()

    rows = load_jsonl(args.input_path)
    validate_records(rows, schema_path("dataset.schema.json"), context_prefix="dataset")

    chunks, idx = build_and_save_index(
        dataset_rows=rows,
        out_chunk_path=args.out_chunk,
        index_dir=args.index_dir,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        embedding_model=args.embedding_model,
        index_type=args.index,
    )

    print("chunks={} mode={} index_dir={}".format(len(chunks), idx.mode, args.index_dir))


if __name__ == "__main__":
    main()
