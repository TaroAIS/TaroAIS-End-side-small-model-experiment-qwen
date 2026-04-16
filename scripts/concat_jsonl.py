#!/usr/bin/env python3
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Concatenate multiple JSONL shards into one file.")
    parser.add_argument("--out", required=True)
    parser.add_argument("inputs", nargs="+")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8", newline="") as out_f:
        for input_path in args.inputs:
            in_path = Path(input_path)
            with in_path.open("r", encoding="utf-8") as in_f:
                for line in in_f:
                    out_f.write(line)

    print("concat done: {} shards -> {}".format(len(args.inputs), out_path))


if __name__ == "__main__":
    main()
