#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm.driver_local import LocalLLMDriver
from training.distill_controller import distill_controller_dataset
from utils.io import dump_jsonl, load_jsonl, load_yaml, write_json
from utils.runtime import schema_path
from utils.schema import validate_records


def _teacher_to_driver_cfg(cfg, run_mode):
    teacher = cfg.get("teacher", {})
    mode = str(run_mode).lower()
    enable_fallback = bool(cfg.get("fallback", {}).get("enable", True))
    if mode == "formal":
        enable_fallback = False
    out = {
        "model": {
            "backend": teacher.get("backend", "local"),
            "name_or_path": teacher.get("name_or_path", "qwen3:4b"),
            "decoding": teacher.get("decoding", {}),
        },
        "local_backend": cfg.get("local_backend", {"base_url": "http://localhost:11434/v1", "request_timeout_s": 120}),
        "fallback": {"enable": enable_fallback, "mode": cfg.get("fallback", {}).get("mode", "heuristic")},
        "runtime": {"run_mode": mode},
    }
    return out


def main():
    parser = argparse.ArgumentParser(description="Distill teacher outputs into student controller training data.")
    parser.add_argument("--teacher_config", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--run_mode", choices=["smoke", "formal"], default="formal")
    args = parser.parse_args()

    t_cfg = load_yaml(args.teacher_config)
    rows = load_jsonl(args.dataset)
    validate_records(rows, schema_path("dataset.schema.json"), context_prefix="dataset")

    driver_cfg = _teacher_to_driver_cfg(t_cfg, run_mode=args.run_mode)
    driver = LocalLLMDriver(driver_cfg)

    distilled, stats = distill_controller_dataset(rows, t_cfg, driver)
    dump_jsonl(args.out, distilled)

    stats_path = str(args.out).replace(".jsonl", "_stats.json")
    write_json(stats_path, stats)

    print("distill done: valid={} total={} -> {}".format(stats.get("valid", 0), stats.get("total", 0), args.out))
    print("stats: {}".format(stats_path))


if __name__ == "__main__":
    main()
