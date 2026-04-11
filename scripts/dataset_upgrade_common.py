#!/usr/bin/env python3
import io
import json
import math
import os
import random
import re
import time
import zipfile
from collections import defaultdict
from pathlib import Path

import requests
import urllib3

from utils.io import dump_jsonl, ensure_dir, write_json


LONG_BENCH_TASKS = {
    "single_doc_qa": ["narrativeqa", "qasper", "multifieldqa_en", "multifieldqa_zh"],
    "multi_doc_qa": ["hotpotqa", "2wikimqa", "musique", "dureader"],
    "code_qa": ["lcc", "repobench-p"],
}

EXT_DATASET_SPECS = {
    "narrativeqa": {
        "task_group": "single_doc_qa",
        "dataset_id": "deepmind/narrativeqa",
        "kind": "parquet",
        "train_prefix": "data/train-",
        "valid_prefix": "data/validation-",
        "source": "huggingface:deepmind/narrativeqa",
    },
    "qasper": {
        "task_group": "single_doc_qa",
        "dataset_id": "allenai/qasper",
        "kind": "rows_api",
        "config": "qasper",
        "train_split": "train",
        "valid_split": "validation",
        "source": "huggingface:allenai/qasper",
    },
    "hotpotqa": {
        "task_group": "multi_doc_qa",
        "dataset_id": "hotpotqa/hotpot_qa",
        "kind": "parquet",
        "train_prefix": "distractor/train-",
        "valid_prefix": "distractor/validation-",
        "source": "huggingface:hotpotqa/hotpot_qa",
    },
    "musique": {
        "task_group": "multi_doc_qa",
        "dataset_id": "dgslibisey/MuSiQue",
        "kind": "jsonl",
        "train_path": "musique_ans_v1.0_train.jsonl",
        "valid_path": "musique_ans_v1.0_dev.jsonl",
        "source": "huggingface:dgslibisey/MuSiQue",
    },
    "repobench_python": {
        "task_group": "code_qa",
        "dataset_id": "tianyang/repobench_python_v1.1",
        "kind": "parquet_split_90_10",
        "all_prefixes": [
            "data/cross_file_first-",
            "data/cross_file_random-",
            "data/in_file-",
        ],
        "source": "huggingface:tianyang/repobench_python_v1.1",
        "language": "python",
    },
    "repobench_java": {
        "task_group": "code_qa",
        "dataset_id": "tianyang/repobench_java_v1.1",
        "kind": "parquet_split_90_10",
        "all_prefixes": [
            "data/cross_file_first-",
            "data/cross_file_random-",
            "data/in_file-",
        ],
        "source": "huggingface:tianyang/repobench_java_v1.1",
        "language": "java",
    },
}

HF_WEB_BASE = os.environ.get("HF_WEB_BASE", "https://huggingface.co").rstrip("/")
HF_API_BASE = os.environ.get("HF_API_BASE", HF_WEB_BASE).rstrip("/")
HF_DATASETS_SERVER_BASE = os.environ.get(
    "HF_DATASETS_SERVER_BASE",
    "https://datasets-server.huggingface.co",
).rstrip("/")


def safe_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    try:
        return list(value)
    except Exception:
        return [value]


def ensure_python(value):
    if isinstance(value, dict):
        return {k: ensure_python(v) for k, v in value.items()}
    if isinstance(value, list):
        return [ensure_python(v) for v in value]
    if hasattr(value, "tolist"):
        try:
            return ensure_python(value.tolist())
        except Exception:
            return value
    return value


def normalize_answer(value):
    if isinstance(value, list):
        for item in value:
            text = safe_text(item)
            if text:
                return text
        return ""
    return safe_text(value)


def split_context_to_documents(context):
    text = safe_text(context)
    if not text:
        return [{"doc_id": "d1", "text": "N/A"}]

    marker = re.compile(r"(?:^|\n)(Passage\s+\d+\s*:)", flags=re.I)
    matches = list(marker.finditer(text))
    if len(matches) <= 1:
        return [{"doc_id": "d1", "text": text}]

    docs = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        label = match.group(1).replace(" ", "_").replace(":", "").lower()
        docs.append({"doc_id": label, "text": body})
    if docs:
        return docs
    return [{"doc_id": "d1", "text": text}]


def task_group_for_longbench(source_task):
    task = str(source_task or "").strip().lower()
    for task_group, names in LONG_BENCH_TASKS.items():
        if task in names:
            return task_group
    return "single_doc_qa"


def dataset_row(sample_id, task, question, documents, answer, meta):
    docs = []
    for idx, doc in enumerate(documents or []):
        text = safe_text((doc or {}).get("text", ""))
        if not text:
            continue
        docs.append(
            {
                "doc_id": safe_text((doc or {}).get("doc_id", "")) or "d{}".format(idx + 1),
                "text": text,
            }
        )
    if not docs:
        docs = [{"doc_id": "d1", "text": "N/A"}]
    return {
        "id": safe_text(sample_id),
        "task": safe_text(task),
        "question": safe_text(question) or "请根据上下文给出答案。",
        "documents": docs,
        "answer": safe_text(answer) or "unknown",
        "meta": ensure_python(meta or {}),
    }


def hf_api_payload(dataset_id):
    url = "{}/api/datasets/{}".format(HF_API_BASE, dataset_id)
    resp = request_with_retry(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def request_with_retry(url, timeout=60, max_attempts=3):
    session = requests.Session()
    session.trust_env = False
    last_exc = None
    for attempt in range(1, int(max_attempts) + 1):
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            last_exc = exc
            if attempt >= int(max_attempts):
                break
            time.sleep(float(attempt))
    for attempt in range(1, int(max_attempts) + 1):
        try:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            resp = session.get(url, timeout=timeout, verify=False)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            last_exc = exc
            if attempt >= int(max_attempts):
                raise
            time.sleep(float(attempt))
    raise last_exc


def hf_resolve_url(dataset_id, rel_path, revision="main"):
    return "{}/datasets/{}/resolve/{}/{}".format(HF_WEB_BASE, dataset_id, revision, rel_path)


def hf_siblings(dataset_id):
    payload = hf_api_payload(dataset_id)
    return payload.get("siblings", []), payload


def parquet_file_urls(dataset_id, prefixes, revision="main"):
    prefixes = [prefixes] if isinstance(prefixes, str) else list(prefixes)
    siblings, payload = hf_siblings(dataset_id)
    out = []
    for item in siblings:
        name = item.get("rfilename", "")
        if not name.endswith(".parquet"):
            continue
        for prefix in prefixes:
            if name.startswith(prefix):
                out.append(hf_resolve_url(dataset_id, name, revision=revision))
                break
    out.sort()
    return out, payload


def load_parquet_rows(urls, max_rows=0):
    import pandas as pd

    rows = []
    remaining = int(max_rows) if max_rows else 0
    for url in urls:
        resp = request_with_retry(url, timeout=300)
        frame = pd.read_parquet(io.BytesIO(resp.content))
        for row in frame.to_dict(orient="records"):
            rows.append(ensure_python(row))
            if remaining:
                remaining -= 1
                if remaining <= 0:
                    return rows
    return rows


def rows_api_iter(dataset_id, config, split, max_rows=0, page_size=100):
    offset = 0
    fetched = 0
    while True:
        length = int(page_size)
        if max_rows:
            length = min(length, int(max_rows) - fetched)
            if length <= 0:
                break
        url = (
            "{}/rows?dataset={}&config={}&split={}&offset={}&length={}"
        ).format(HF_DATASETS_SERVER_BASE, dataset_id, config, split, offset, length)
        resp = request_with_retry(url, timeout=120)
        payload = resp.json()
        rows = payload.get("rows", [])
        if not rows:
            break
        for item in rows:
            yield ensure_python(item.get("row", {}))
            fetched += 1
        offset += len(rows)
        if len(rows) < length:
            break


def download_zip(dataset_id, rel_path, revision="main"):
    url = hf_resolve_url(dataset_id, rel_path, revision=revision)
    resp = request_with_retry(url, timeout=300)
    return zipfile.ZipFile(io.BytesIO(resp.content))


def download_jsonl_rows(dataset_id, rel_path, revision="main", max_rows=0):
    url = hf_resolve_url(dataset_id, rel_path, revision=revision)
    resp = request_with_retry(url, timeout=300)
    rows = []
    for line in resp.text.splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
        if max_rows and len(rows) >= int(max_rows):
            break
    return rows


def write_registry_and_versions(registry_path, versions_path, registry, versions):
    write_json(registry_path, registry)
    write_json(versions_path, versions)


def load_narrativeqa_full_text(max_rows=0):
    zip_file = download_zip("deepmind/narrativeqa", "data/narrativeqa_full_text.zip")
    out = {}
    needed = int(max_rows) if max_rows else 0
    for name in zip_file.namelist():
        if not name.endswith(".content"):
            continue
        doc_id = Path(name).stem
        text = zip_file.read(name).decode("utf-8", errors="ignore")
        out[doc_id] = text
        if needed:
            needed -= 1
            if needed <= 0:
                break
    return out


def assign_length_bins(rows):
    values = sorted([context_chars(row) for row in rows])
    if not values:
        return {}
    n = len(values)
    q1 = values[min(n - 1, int((n - 1) * 0.25))]
    q2 = values[min(n - 1, int((n - 1) * 0.50))]
    q3 = values[min(n - 1, int((n - 1) * 0.75))]
    out = {}
    for row in rows:
        rid = row.get("id", "")
        value = context_chars(row)
        if value <= q1:
            out[rid] = "q1"
        elif value <= q2:
            out[rid] = "q2"
        elif value <= q3:
            out[rid] = "q3"
        else:
            out[rid] = "q4"
    return out


def context_chars(row):
    return int(sum([len((doc or {}).get("text", "")) for doc in row.get("documents", [])]))


def stratify_rows(rows, bin_map):
    groups = defaultdict(list)
    for row in rows:
        key = "{}|{}".format(row.get("task", "unknown"), bin_map.get(row.get("id", ""), "q4"))
        groups[key].append(row)
    return groups


def allocate_quotas(groups, target_n):
    keys = sorted(groups.keys())
    total = float(sum([len(groups[key]) for key in keys]) or 1.0)
    quota = {}
    frac = []
    for key in keys:
        cap = len(groups[key])
        expected = (cap / total) * float(target_n)
        base = min(cap, int(math.floor(expected)))
        quota[key] = base
        frac.append((expected - float(base), key))
    used = sum(quota.values())
    remain = max(0, int(target_n) - int(used))
    for _, key in sorted(frac, key=lambda item: (-item[0], item[1])):
        if remain <= 0:
            break
        if quota[key] < len(groups[key]):
            quota[key] += 1
            remain -= 1
    return quota


def sample_stratified(rows, target_n, seed=42):
    if target_n <= 0:
        return []
    if target_n >= len(rows):
        out = list(rows)
        random.Random(int(seed)).shuffle(out)
        return out
    rng = random.Random(int(seed))
    bins = assign_length_bins(rows)
    groups = stratify_rows(rows, bins)
    for key in groups:
        rng.shuffle(groups[key])
    quota = allocate_quotas(groups, target_n)
    selected = []
    leftovers = []
    for key in sorted(groups.keys()):
        take = min(quota.get(key, 0), len(groups[key]))
        selected.extend(groups[key][:take])
        leftovers.extend(groups[key][take:])
    if len(selected) < target_n:
        rng.shuffle(leftovers)
        selected.extend(leftovers[: target_n - len(selected)])
    rng.shuffle(selected)
    return selected[:target_n]


def task_counts(rows):
    out = defaultdict(int)
    for row in rows:
        out[row.get("task", "unknown")] += 1
    return dict(out)


def split_train_valid(rows, seed=42, valid_ratio=0.1, stratify_key_fn=None):
    rng = random.Random(int(seed))
    groups = defaultdict(list)
    for row in rows:
        if stratify_key_fn is None:
            key = row.get("task", "unknown")
        else:
            key = stratify_key_fn(row)
        groups[key].append(row)

    train = []
    valid = []
    for key in sorted(groups.keys()):
        block = list(groups[key])
        rng.shuffle(block)
        if len(block) <= 1:
            train.extend(block)
            continue
        n_valid = int(round(len(block) * float(valid_ratio)))
        n_valid = max(1, min(len(block) - 1, n_valid))
        valid.extend(block[:n_valid])
        train.extend(block[n_valid:])
    rng.shuffle(train)
    rng.shuffle(valid)
    return train, valid


def dump_rows(path, rows):
    ensure_dir(Path(path).parent)
    dump_jsonl(path, rows)
