#!/usr/bin/env python3
import argparse
import hashlib
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.io import dump_jsonl, load_jsonl, write_json
from utils.runtime import schema_path
from utils.schema import validate_records


def _context_chars(row):
    return int(sum([len((d or {}).get("text", "")) for d in row.get("documents", [])]))


def _assign_length_bins(rows):
    vals = sorted([_context_chars(r) for r in rows])
    if not vals:
        return {}
    n = len(vals)
    q1 = vals[min(n - 1, int((n - 1) * 0.25))]
    q2 = vals[min(n - 1, int((n - 1) * 0.50))]
    q3 = vals[min(n - 1, int((n - 1) * 0.75))]

    bins = {}
    for r in rows:
        rid = r.get("id", "")
        v = _context_chars(r)
        if v <= q1:
            b = "q1"
        elif v <= q2:
            b = "q2"
        elif v <= q3:
            b = "q3"
        else:
            b = "q4"
        bins[rid] = b
    return bins


def _stratify(rows, bin_map):
    groups = defaultdict(list)
    for r in rows:
        key = "{}|{}".format(r.get("task", "unknown"), bin_map.get(r.get("id", ""), "q4"))
        groups[key].append(r)
    return groups


def _stable_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _allocate(groups, target_n):
    keys = sorted(groups.keys())
    total = float(sum([len(groups[k]) for k in keys]) or 1.0)

    quota = {}
    frac = []
    for k in keys:
        cap = len(groups[k])
        expected = (cap / total) * float(target_n)
        base = int(math.floor(expected))
        base = min(base, cap)
        quota[k] = base
        frac.append((expected - float(base), k))

    used = sum(quota.values())
    remain = max(0, int(target_n) - int(used))
    for _, k in sorted(frac, key=lambda x: (-x[0], x[1])):
        if remain <= 0:
            break
        if quota[k] < len(groups[k]):
            quota[k] += 1
            remain -= 1

    return quota


def _sample_stratified(rows, target_n, rng):
    if target_n <= 0:
        return []
    if target_n >= len(rows):
        out = list(rows)
        rng.shuffle(out)
        return out

    bin_map = _assign_length_bins(rows)
    groups = _stratify(rows, bin_map)
    for k in groups.keys():
        rng.shuffle(groups[k])

    quota = _allocate(groups, target_n)
    selected = []
    leftovers = []
    for k in sorted(groups.keys()):
        take = min(quota.get(k, 0), len(groups[k]))
        selected.extend(groups[k][:take])
        leftovers.extend(groups[k][take:])

    if len(selected) < target_n:
        rng.shuffle(leftovers)
        selected.extend(leftovers[: target_n - len(selected)])

    rng.shuffle(selected)
    return selected[:target_n]


def _manifest_counts(rows):
    out = {}
    for r in rows:
        task = r.get("task", "unknown")
        out[task] = out.get(task, 0) + 1
    return out


def main():
    parser = argparse.ArgumentParser(
        description="Build extended evaluation sets with stratified sampling."
    )
    parser.add_argument("--train", default="data/train_ext/combined_train.jsonl")
    parser.add_argument("--valid", default="data/train_ext/combined_valid.jsonl")
    parser.add_argument("--canonical", default="data/main_eval/longbench_3tasks_test.jsonl")
    parser.add_argument("--out_ext", default="data/train_ext/combined_valid.jsonl")
    parser.add_argument("--out_dev", default="data/main_eval/longbench_3tasks_dev100.jsonl")
    parser.add_argument("--out_holdout", default="data/main_eval/longbench_3tasks_holdout100.jsonl")
    parser.add_argument(
        "--manifest",
        default="data/manifests/main_eval_split_manifest_legacy.json",
    )
    parser.add_argument("--target_total", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260219)
    args = parser.parse_args()

    rng = random.Random(int(args.seed))

    train_rows = load_jsonl(args.train)
    valid_rows = load_jsonl(args.valid)
    canonical_rows = load_jsonl(args.canonical)

    canonical_ids = set([r.get("id", "") for r in canonical_rows])
    pool = []
    seen = set()
    for r in train_rows + valid_rows:
        rid = r.get("id", "")
        if not rid or rid in canonical_ids or rid in seen:
            continue
        seen.add(rid)
        pool.append(r)

    target_total = min(int(args.target_total), len(pool))
    ext_rows = _sample_stratified(pool, target_total, rng)
    dev_n = int(target_total // 2)
    holdout_n = int(target_total - dev_n)
    dev_rows = _sample_stratified(ext_rows, dev_n, rng)
    dev_ids = set([r.get("id", "") for r in dev_rows])
    holdout_candidates = [r for r in ext_rows if r.get("id", "") not in dev_ids]
    holdout_rows = _sample_stratified(holdout_candidates, holdout_n, rng)

    # Schema and overlap checks.
    validate_records(ext_rows, schema_path("dataset.schema.json"), context_prefix="ext_eval")
    validate_records(dev_rows, schema_path("dataset.schema.json"), context_prefix="dev_eval")
    validate_records(
        holdout_rows,
        schema_path("dataset.schema.json"),
        context_prefix="holdout_eval",
    )

    dev_id_set = set([r.get("id", "") for r in dev_rows])
    holdout_id_set = set([r.get("id", "") for r in holdout_rows])
    ext_id_set = set([r.get("id", "") for r in ext_rows])
    if dev_id_set & holdout_id_set:
        raise RuntimeError("dev and holdout overlap detected.")
    if ext_id_set & canonical_ids:
        raise RuntimeError("extended eval overlaps canonical test ids.")

    dump_jsonl(args.out_ext, ext_rows)
    dump_jsonl(args.out_dev, dev_rows)
    dump_jsonl(args.out_holdout, holdout_rows)

    manifest = {
        "seed": int(args.seed),
        "target_total": int(target_total),
        "source": {
            "train": str(args.train),
            "valid": str(args.valid),
            "canonical": str(args.canonical),
        },
        "sizes": {
            "pool": int(len(pool)),
            "ext": int(len(ext_rows)),
            "dev": int(len(dev_rows)),
            "holdout": int(len(holdout_rows)),
        },
        "task_counts": {
            "ext": _manifest_counts(ext_rows),
            "dev": _manifest_counts(dev_rows),
            "holdout": _manifest_counts(holdout_rows),
        },
        "ids": {
            "ext": sorted(list(ext_id_set)),
            "dev": sorted(list(dev_id_set)),
            "holdout": sorted(list(holdout_id_set)),
        },
        "sha256": {
            "ext": _stable_sha256(args.out_ext),
            "dev": _stable_sha256(args.out_dev),
            "holdout": _stable_sha256(args.out_holdout),
        },
    }
    write_json(args.manifest, manifest)

    print("ext: {} -> {}".format(len(ext_rows), args.out_ext))
    print("dev: {} -> {}".format(len(dev_rows), args.out_dev))
    print("holdout: {} -> {}".format(len(holdout_rows), args.out_holdout))
    print("manifest -> {}".format(args.manifest))


if __name__ == "__main__":
    main()
