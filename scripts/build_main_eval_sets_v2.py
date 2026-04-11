#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dataset_upgrade_common import sample_stratified, task_counts
from utils.io import dump_jsonl, load_jsonl, write_json
from utils.runtime import schema_path
from utils.schema import validate_records


def main():
    parser = argparse.ArgumentParser(description="Build main-eval dev/holdout sets from combined valid pool.")
    parser.add_argument("--valid", default="data/train_ext/combined_valid.jsonl")
    parser.add_argument("--canonical", default="data/main_eval/longbench_3tasks_test.jsonl")
    parser.add_argument("--out_dev", default="data/main_eval/longbench_3tasks_dev100.jsonl")
    parser.add_argument("--out_holdout", default="data/main_eval/longbench_3tasks_holdout100.jsonl")
    parser.add_argument("--manifest", default="data/manifests/main_eval_split_manifest.json")
    parser.add_argument("--dev_size", type=int, default=100)
    parser.add_argument("--holdout_size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260411)
    args = parser.parse_args()

    valid_rows = load_jsonl(args.valid)
    canonical_rows = load_jsonl(args.canonical)
    canonical_ids = set([row.get("id", "") for row in canonical_rows])
    pool = [row for row in valid_rows if row.get("id", "") not in canonical_ids]

    dev_rows = sample_stratified(pool, min(int(args.dev_size), len(pool)), seed=args.seed)
    dev_ids = set([row.get("id", "") for row in dev_rows])
    holdout_pool = [row for row in pool if row.get("id", "") not in dev_ids]
    holdout_rows = sample_stratified(
        holdout_pool,
        min(int(args.holdout_size), len(holdout_pool)),
        seed=int(args.seed) + 1,
    )

    validate_records(dev_rows, schema_path("dataset.schema.json"), context_prefix="main_eval_dev")
    validate_records(holdout_rows, schema_path("dataset.schema.json"), context_prefix="main_eval_holdout")

    dump_jsonl(args.out_dev, dev_rows)
    dump_jsonl(args.out_holdout, holdout_rows)

    manifest = {
        "source": {"valid": args.valid, "canonical": args.canonical},
        "outputs": {"dev": args.out_dev, "holdout": args.out_holdout},
        "seed": int(args.seed),
        "sizes": {
            "pool": len(pool),
            "dev": len(dev_rows),
            "holdout": len(holdout_rows),
        },
        "task_counts": {
            "dev": task_counts(dev_rows),
            "holdout": task_counts(holdout_rows),
        },
        "ids": {
            "dev": sorted(list(dev_ids)),
            "holdout": sorted(list([row.get("id", "") for row in holdout_rows])),
        },
    }
    write_json(args.manifest, manifest)

    print("main eval dev={} -> {}".format(len(dev_rows), args.out_dev))
    print("main eval holdout={} -> {}".format(len(holdout_rows), args.out_holdout))


if __name__ == "__main__":
    main()
