#!/usr/bin/env python3
import copy
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = REPO_ROOT / "configs" / "agent_qwen3_4b_fast.yaml"


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump_yaml(path: Path, data):
    with path.open("w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=False)


def make_multi_doc_only_lift(base_cfg):
    cfg = copy.deepcopy(base_cfg)
    cfg["experiment"]["profile"] = "canonical_qwen3_4b_round6_multi_doc_only_lift"
    cfg["experiment"]["objective"] = "canonical_round6_surgical_multi_doc_lift"
    md = cfg["agent"]["task_overrides"]["multi_doc_qa"]
    md["top_k_init"] = 3
    md["forced_retrieve"]["top_k_extra"] = 2
    return cfg


def make_code_only_lift(base_cfg):
    cfg = copy.deepcopy(base_cfg)
    cfg["experiment"]["profile"] = "canonical_qwen3_4b_round6_code_only_lift"
    cfg["experiment"]["objective"] = "canonical_round6_surgical_code_lift"
    code = cfg["agent"]["task_overrides"]["code_qa"]
    code["top_k_init"] = 3
    code["max_new_tokens"] = 176
    return cfg


def main():
    base_cfg = load_yaml(BASE_CONFIG)
    outputs = {
        REPO_ROOT / "configs" / "agent_round6_multi_doc_only_lift.yaml": make_multi_doc_only_lift(base_cfg),
        REPO_ROOT / "configs" / "agent_round6_code_only_lift.yaml": make_code_only_lift(base_cfg),
    }
    for path, cfg in outputs.items():
        dump_yaml(path, cfg)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
