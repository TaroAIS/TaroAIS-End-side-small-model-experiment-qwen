#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.io import dump_jsonl, load_jsonl, write_json
from utils.runtime import schema_path
from utils.schema import validate_records


def _merge_unique(paths):
    rows = []
    seen = set()
    for path in paths:
        for row in load_jsonl(path):
            rid = str(row.get("id", "") or "")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description="Merge per-task extension corpora into combined train/valid sets.")
    parser.add_argument("--single_doc_dir", default="data/train_ext/single_doc")
    parser.add_argument("--multi_doc_dir", default="data/train_ext/multi_doc")
    parser.add_argument("--code_dir", default="data/train_ext/code_qa")
    parser.add_argument("--out_train", default="data/train_ext/combined_train.jsonl")
    parser.add_argument("--out_valid", default="data/train_ext/combined_valid.jsonl")
    parser.add_argument("--manifest", default="data/manifests/combined_ext_manifest.json")
    args = parser.parse_args()

    train_paths = [
        str(Path(args.single_doc_dir) / "merged_train.jsonl"),
        str(Path(args.multi_doc_dir) / "merged_train.jsonl"),
        str(Path(args.code_dir) / "merged_train.jsonl"),
    ]
    valid_paths = [
        str(Path(args.single_doc_dir) / "merged_valid.jsonl"),
        str(Path(args.multi_doc_dir) / "merged_valid.jsonl"),
        str(Path(args.code_dir) / "merged_valid.jsonl"),
    ]

    train_rows = _merge_unique(train_paths)
    valid_rows = _merge_unique(valid_paths)

    validate_records(train_rows, schema_path("dataset.schema.json"), context_prefix="combined_train")
    validate_records(valid_rows, schema_path("dataset.schema.json"), context_prefix="combined_valid")

    dump_jsonl(args.out_train, train_rows)
    dump_jsonl(args.out_valid, valid_rows)

    manifest = {
        "inputs": {"train": train_paths, "valid": valid_paths},
        "outputs": {"train": args.out_train, "valid": args.out_valid},
        "counts": {"train": len(train_rows), "valid": len(valid_rows)},
        "task_counts": {
            "train": _task_counts(train_rows),
            "valid": _task_counts(valid_rows),
        },
    }
    write_json(args.manifest, manifest)
    print("combined train={} -> {}".format(len(train_rows), args.out_train))
    print("combined valid={} -> {}".format(len(valid_rows), args.out_valid))


def _task_counts(rows):
    out = {}
    for row in rows:
        task = row.get("task", "unknown")
        out[task] = out.get(task, 0) + 1
    return out


if __name__ == "__main__":
    main()
