#!/usr/bin/env python3
import argparse
import copy
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.io import dump_jsonl, load_jsonl, write_json


def sample_rows(rows, n, seed):
    if n <= 0 or n >= len(rows):
        return list(rows)
    rng = random.Random(seed)
    picks = list(rows)
    rng.shuffle(picks)
    return picks[:n]


def annotate_rows(rows, source_name, seed, per_source):
    out = []
    for idx, row in enumerate(rows, start=1):
        item = copy.deepcopy(row)
        item["id"] = "appendix_{}_{}_{}".format(source_name, idx, row.get("id", "sample"))
        meta = dict(item.get("meta") or {})
        meta["eval_track"] = "code_generalization_appendix"
        meta["appendix_source"] = source_name
        meta["appendix_seed"] = int(seed)
        meta["appendix_per_source"] = int(per_source)
        item["meta"] = meta
        out.append(item)
    return out


def main():
    ap = argparse.ArgumentParser(description="Build a small code-QA appendix set from RepoBench valid splits.")
    ap.add_argument("--python_valid", default="data/train_ext/code_qa/repobench_python_valid.jsonl")
    ap.add_argument("--java_valid", default="data/train_ext/code_qa/repobench_java_valid.jsonl")
    ap.add_argument("--out_dir", default="data/main_eval/code_generalization")
    ap.add_argument("--manifest", default="data/manifests/code_generalization_appendix_manifest.json")
    ap.add_argument("--per_source", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    python_path = ROOT / args.python_valid
    java_path = ROOT / args.java_valid
    if not python_path.exists() or not java_path.exists():
        missing = []
        if not python_path.exists():
            missing.append(str(python_path))
        if not java_path.exists():
            missing.append(str(java_path))
        raise FileNotFoundError(
            "Missing RepoBench valid files for appendix build: {}. Run scripts/prepare_task_ext_corpus.py first.".format(
                "; ".join(missing)
            )
        )

    python_rows = [row for row in load_jsonl(python_path) if row.get("task") == "code_qa"]
    java_rows = [row for row in load_jsonl(java_path) if row.get("task") == "code_qa"]
    if not python_rows or not java_rows:
        raise RuntimeError("RepoBench appendix source files do not contain code_qa rows.")

    py_sample = annotate_rows(sample_rows(python_rows, args.per_source, args.seed), "repobench_python_valid", args.seed, args.per_source)
    java_sample = annotate_rows(sample_rows(java_rows, args.per_source, args.seed + 1), "repobench_java_valid", args.seed, args.per_source)

    combined = list(py_sample) + list(java_sample)
    random.Random(args.seed).shuffle(combined)

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    py_out = out_dir / "repobench_python_appendix.jsonl"
    java_out = out_dir / "repobench_java_appendix.jsonl"
    combined_out = out_dir / "code_generalization_appendix.jsonl"

    dump_jsonl(py_out, py_sample)
    dump_jsonl(java_out, java_sample)
    dump_jsonl(combined_out, combined)

    write_json(
        ROOT / args.manifest,
        {
            "status": "generated",
            "seed": int(args.seed),
            "per_source": int(args.per_source),
            "sources": {
                "repobench_python_valid": args.python_valid,
                "repobench_java_valid": args.java_valid,
            },
            "outputs": {
                "repobench_python_appendix": str(py_out.relative_to(ROOT)),
                "repobench_java_appendix": str(java_out.relative_to(ROOT)),
                "code_generalization_appendix": str(combined_out.relative_to(ROOT)),
            },
            "counts": {
                "repobench_python_appendix": len(py_sample),
                "repobench_java_appendix": len(java_sample),
                "code_generalization_appendix": len(combined),
            },
            "notes": [
                "This appendix set is supplementary only and does not replace LongBench_3tasks canonical.",
                "It is used to broaden code-QA external validity with fixed-size RepoBench Python and Java valid samples.",
            ],
        },
        indent=2,
    )

    print("code_generalization_appendix -> {}".format(combined_out))


if __name__ == "__main__":
    main()
