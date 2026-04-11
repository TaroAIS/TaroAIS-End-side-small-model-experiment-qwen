#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dataset_upgrade_common import (
    LONG_BENCH_TASKS,
    dataset_row,
    download_zip,
    dump_rows,
    hf_api_payload,
    normalize_answer,
    safe_text,
    split_context_to_documents,
    task_counts,
    task_group_for_longbench,
)
from utils.io import write_json
from utils.runtime import schema_path
from utils.schema import validate_records


DEFAULT_DATASET = "zai-org/LongBench"


def _selected_files():
    out = []
    for names in LONG_BENCH_TASKS.values():
        for name in names:
            out.append("data/{}.jsonl".format(name))
    return out


def _normalize_rows(file_name, zip_file, max_rows=0):
    source_task = Path(file_name).stem
    task_group = task_group_for_longbench(source_task)
    lines = zip_file.read(file_name).decode("utf-8").splitlines()
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        raw = json.loads(line)
        sample_id = "lb_{}_{}".format(source_task, safe_text(raw.get("_id", ""))[:40])
        row = dataset_row(
            sample_id=sample_id,
            task=task_group,
            question=safe_text(raw.get("input", "")) or "请根据上下文给出答案。",
            documents=split_context_to_documents(raw.get("context", "")),
            answer=normalize_answer(raw.get("answers", [])),
            meta={
                "source": "huggingface:{}".format(DEFAULT_DATASET),
                "source_task": source_task,
                "source_language": safe_text(raw.get("language", "")),
                "source_length": raw.get("length"),
                "source_dataset_field": safe_text(raw.get("dataset", "")),
                "task_group": task_group,
            },
        )
        out.append(row)
        if max_rows and len(out) >= int(max_rows):
            break
    return out


def main():
    parser = argparse.ArgumentParser(description="Prepare LongBench 3-task canonical evaluation set.")
    parser.add_argument("--dataset_id", default=DEFAULT_DATASET)
    parser.add_argument("--revision", default="main")
    parser.add_argument("--out_test", default="data/main_eval/longbench_3tasks_test.jsonl")
    parser.add_argument(
        "--source_meta",
        default="data/manifests/longbench_3tasks_source.json",
        help="Write source/version metadata here.",
    )
    parser.add_argument(
        "--registry",
        default="data/manifests/dataset_registry.json",
        help="Optional registry file to update/create.",
    )
    parser.add_argument("--versions", default="data/manifests/dataset_versions.json")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max_samples", type=int, default=0)
    args = parser.parse_args()

    zip_file = download_zip(args.dataset_id, "data.zip", revision=args.revision)
    selected_files = _selected_files()
    rows = []
    for file_name in selected_files:
        if file_name not in zip_file.namelist():
            raise RuntimeError("LongBench file missing from archive: {}".format(file_name))
        per_file_limit = 0
        if args.max_samples:
            per_file_limit = max(1, int(args.max_samples))
        rows.extend(_normalize_rows(file_name, zip_file, max_rows=per_file_limit))

    validate_records(rows, schema_path("dataset.schema.json"), context_prefix="longbench_3tasks_test")
    dump_rows(args.out_test, rows)

    payload = hf_api_payload(args.dataset_id)
    meta = {
        "mode": "remote",
        "source": "huggingface:{}".format(args.dataset_id),
        "revision_requested": args.revision,
        "revision_resolved": payload.get("sha", args.revision),
        "upstream_last_modified": payload.get("lastModified"),
        "selected_tasks": LONG_BENCH_TASKS,
        "selected_files": selected_files,
        "n_total": len(rows),
        "task_counts": task_counts(rows),
        "seed": int(args.seed),
        "max_samples_per_task": int(args.max_samples or 0),
        "output": str(args.out_test),
    }
    write_json(args.source_meta, meta)

    registry_path = Path(args.registry)
    registry = {}
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception:
            registry = {}
    registry["main_eval"] = {
        "canonical": str(args.out_test),
        "source_meta": str(args.source_meta),
        "dataset_id": args.dataset_id,
        "selected_tasks": LONG_BENCH_TASKS,
    }
    write_json(args.registry, registry)

    versions_path = Path(args.versions)
    if versions_path.exists():
        try:
            versions = json.loads(versions_path.read_text(encoding="utf-8"))
        except Exception:
            versions = {}
    else:
        versions = {}
    versions["main_eval"] = {
        "dataset_id": args.dataset_id,
        "revision_resolved": payload.get("sha", args.revision),
        "upstream_last_modified": payload.get("lastModified"),
        "n_total": len(rows),
        "task_counts": task_counts(rows),
    }
    write_json(args.versions, versions)

    print("longbench_3tasks canonical -> {}".format(args.out_test))
    print("samples={} task_counts={}".format(len(rows), json.dumps(task_counts(rows), ensure_ascii=False)))


if __name__ == "__main__":
    main()
