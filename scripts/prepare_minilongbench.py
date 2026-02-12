#!/usr/bin/env python3
import argparse
import copy
import json
import random
import re
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests

from utils.io import dump_jsonl, load_jsonl, write_json
from utils.schema import validate_records
from utils.runtime import project_root, schema_path

DEFAULT_HF_DATASET = "linggm/MiniLongBench"
# Pinned revision from HuggingFace dataset metadata (fetched 2026-02-12).
DEFAULT_HF_REVISION = "0ba7bf46265f1f783653693fb6b581f617f37275"


def _expand_rows(base_rows, split, n):
    out = []
    if not base_rows:
        return out
    for i in range(n):
        src = base_rows[i % len(base_rows)]
        row = copy.deepcopy(src)
        row["id"] = "{}_{}_{}".format(src.get("id", "sample"), split, i + 1)
        out.append(row)
    return out


def _build_offline_dataset():
    root = project_root()
    tiny_path = root / "smoke_data" / "minilongbench_tiny.jsonl"
    tiny = load_jsonl(tiny_path)
    return {
        "train": _expand_rows(tiny, "train", 30),
        "valid": _expand_rows(tiny, "valid", 9),
        "test": _expand_rows(tiny, "test", 12),
    }


def _http_get_json(url, timeout=60):
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _http_get_text(url, timeout=120):
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _list_hf_task_files(dataset_id):
    api_url = "https://huggingface.co/api/datasets/{}".format(dataset_id)
    payload = _http_get_json(api_url, timeout=60)
    siblings = payload.get("siblings", [])
    files = []
    for item in siblings:
        name = item.get("rfilename", "")
        if name.startswith("data/") and name.endswith(".jsonl"):
            files.append(name)
    files.sort()
    return files, payload


def _safe_text(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return str(v).strip()


def _split_context_to_documents(context):
    text = _safe_text(context)
    if not text:
        return [{"doc_id": "d1", "text": "N/A"}]

    # Common MiniLongBench style: Passage 1:, Passage 2:, ...
    marker = re.compile(r"(?:^|\n)(Passage\s+\d+\s*:)", flags=re.I)
    matches = list(marker.finditer(text))
    if len(matches) <= 1:
        return [{"doc_id": "d1", "text": text}]

    docs = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        label = m.group(1).replace(" ", "_").replace(":", "").lower()
        docs.append({"doc_id": label, "text": body})

    if not docs:
        return [{"doc_id": "d1", "text": text}]
    return docs


def _map_task_type(source_task, language, context):
    task = (source_task or "").lower()
    lang = (language or "").lower()

    code_tasks = set(["lcc", "repobench-p"])
    multi_doc_tasks = set(["2wikimqa", "hotpotqa", "musique", "multi_news", "qmsum"])

    if task in code_tasks or lang in set(["python", "java", "cpp", "javascript", "go"]):
        return "code_qa"
    if task in multi_doc_tasks:
        return "multi_doc_qa"
    if re.search(r"Passage\s+2\s*:", _safe_text(context), flags=re.I):
        return "multi_doc_qa"
    return "single_doc_qa"


def _normalize_answer(raw_answers):
    if isinstance(raw_answers, list):
        if not raw_answers:
            return ""
        return _safe_text(raw_answers[0])
    return _safe_text(raw_answers)


def _load_remote_raw_rows(dataset_id, revision):
    task_files, meta = _list_hf_task_files(dataset_id)
    if not task_files:
        raise RuntimeError("No task files discovered under data/*.jsonl for {}".format(dataset_id))

    all_rows = []
    for rel_path in task_files:
        url = "https://huggingface.co/datasets/{}/resolve/{}/{}".format(dataset_id, revision, rel_path)
        text = _http_get_text(url, timeout=120)

        source_task = Path(rel_path).stem
        for idx, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception as exc:
                raise RuntimeError("Invalid JSON in {} line {}: {}".format(rel_path, idx, exc))

            q = _safe_text(obj.get("input"))
            ctx = _safe_text(obj.get("context"))
            ans = _normalize_answer(obj.get("answers"))
            sid = _safe_text(obj.get("_id")) or "{}_{}".format(source_task, idx)

            # Keep non-empty fields for schema compatibility.
            question = q if q else "请根据上下文给出答案。"
            docs = _split_context_to_documents(ctx)
            answer = ans if ans else "unknown"
            task_type = _map_task_type(source_task, obj.get("language"), ctx)

            row = {
                "id": "mlb_{}_{}".format(source_task, sid[:24]),
                "task": task_type,
                "question": question,
                "documents": docs,
                "answer": answer,
                "meta": {
                    "source": "huggingface:{}".format(dataset_id),
                    "source_revision": revision,
                    "source_task": source_task,
                    "source_language": _safe_text(obj.get("language")),
                    "source_length": obj.get("length"),
                    "source_dataset_field": _safe_text(obj.get("dataset")),
                },
            }
            all_rows.append(row)

    return all_rows, task_files, meta


def _stratified_split(rows, seed=42, train_ratio=0.8, valid_ratio=0.1):
    rng = random.Random(int(seed))
    groups = defaultdict(list)

    for row in rows:
        m = row.get("meta", {})
        key = m.get("source_task", row.get("task", "unknown"))
        groups[key].append(row)

    train = []
    valid = []
    test = []

    for key in sorted(groups.keys()):
        chunk = list(groups[key])
        rng.shuffle(chunk)
        n = len(chunk)

        if n == 1:
            n_train = 0
            n_valid = 0
        elif n == 2:
            n_train = 1
            n_valid = 0
        else:
            n_train = int(round(n * float(train_ratio)))
            n_valid = int(round(n * float(valid_ratio)))
            n_train = max(1, min(n - 2, n_train))
            n_valid = max(1, min(n - n_train - 1, n_valid))

        n_test = n - n_train - n_valid
        if n_test < 1:
            if n_valid > 1:
                n_valid -= 1
            elif n_train > 1:
                n_train -= 1
            n_test = n - n_train - n_valid

        train.extend(chunk[:n_train])
        valid.extend(chunk[n_train : n_train + n_valid])
        test.extend(chunk[n_train + n_valid :])

    rng.shuffle(train)
    rng.shuffle(valid)
    rng.shuffle(test)
    return {"train": train, "valid": valid, "test": test}


def build_dataset(mode="remote", dataset_id=DEFAULT_HF_DATASET, revision=DEFAULT_HF_REVISION, seed=42, train_ratio=0.8, valid_ratio=0.1, max_samples=0, strict_remote=False):
    if mode == "offline":
        source_meta = {
            "mode": "offline",
            "source": "local:smoke_data/minilongbench_tiny.jsonl",
            "revision": "local",
            "notes": "expanded from local smoke dataset",
        }
        return _build_offline_dataset(), source_meta

    try:
        raw_rows, task_files, meta = _load_remote_raw_rows(dataset_id=dataset_id, revision=revision)
        if max_samples and int(max_samples) > 0:
            raw_rows = raw_rows[: int(max_samples)]

        split = _stratified_split(
            raw_rows,
            seed=seed,
            train_ratio=train_ratio,
            valid_ratio=valid_ratio,
        )

        source_meta = {
            "mode": "remote",
            "source": "huggingface:{}".format(dataset_id),
            "revision_requested": revision,
            "revision_resolved": meta.get("sha", revision),
            "upstream_last_modified": meta.get("lastModified"),
            "task_files": task_files,
            "n_total": len(raw_rows),
            "n_train": len(split.get("train", [])),
            "n_valid": len(split.get("valid", [])),
            "n_test": len(split.get("test", [])),
        }
        return split, source_meta
    except Exception as exc:
        if strict_remote:
            raise
        fallback = _build_offline_dataset()
        source_meta = {
            "mode": "remote_fallback_offline",
            "source": "local:smoke_data/minilongbench_tiny.jsonl",
            "revision_requested": revision,
            "fallback_reason": str(exc),
            "notes": "remote unavailable, fallback to offline smoke expansion",
        }
        return fallback, source_meta


def main():
    parser = argparse.ArgumentParser(description="Prepare MiniLongBench dataset in project JSONL schema.")
    parser.add_argument("--out", default="data/minilongbench_{split}.jsonl", help="Output path pattern with {split} placeholder.")
    parser.add_argument("--split", default="all", choices=["train", "valid", "test", "all"], help="Split to generate.")
    parser.add_argument("--mode", default="remote", choices=["offline", "remote"], help="Data source mode. remote downloads official MiniLongBench files.")
    parser.add_argument("--remote_dataset", default=DEFAULT_HF_DATASET, help="HuggingFace dataset id for MiniLongBench.")
    parser.add_argument("--revision", default=DEFAULT_HF_REVISION, help="Dataset revision (commit/tag/branch).")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic split.")
    parser.add_argument("--train_ratio", type=float, default=0.8, help="Train split ratio for generated split.")
    parser.add_argument("--valid_ratio", type=float, default=0.1, help="Valid split ratio for generated split.")
    parser.add_argument("--max_samples", type=int, default=0, help="Optional limit for quick debug runs; 0 means full.")
    parser.add_argument("--strict_remote", action="store_true", help="Fail when remote download fails instead of offline fallback.")
    parser.add_argument("--source_meta", default="data/minilongbench_source.json", help="Where to write dataset source/version metadata.")
    args = parser.parse_args()

    datasets, source_meta = build_dataset(
        mode=args.mode,
        dataset_id=args.remote_dataset,
        revision=args.revision,
        seed=args.seed,
        train_ratio=args.train_ratio,
        valid_ratio=args.valid_ratio,
        max_samples=args.max_samples,
        strict_remote=args.strict_remote,
    )

    selected = [args.split] if args.split != "all" else ["train", "valid", "test"]
    schema = schema_path("dataset.schema.json")

    for split in selected:
        rows = datasets.get(split, [])
        validate_records(rows, schema, context_prefix="dataset_{}".format(split))
        out_path = Path(args.out.format(split=split))
        dump_jsonl(out_path, rows)
        print("wrote {} samples to {}".format(len(rows), out_path))

    write_json(args.source_meta, source_meta)
    print("source metadata -> {}".format(args.source_meta))


if __name__ == "__main__":
    main()
