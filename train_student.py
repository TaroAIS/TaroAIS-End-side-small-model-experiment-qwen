#!/usr/bin/env python3
import argparse

from training.train_qlora import train_student_model


def main():
    parser = argparse.ArgumentParser(description="Train student controller with QLoRA config.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--train", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--prefer_real", action="store_true", help="Try real training stack if available.")
    args = parser.parse_args()

    summary = train_student_model(
        config_path=args.config,
        train_path=args.train,
        out_dir=args.out_dir,
        prefer_real=args.prefer_real,
    )
    print("student training finished: {}".format(summary.get("mode", "unknown")))


if __name__ == "__main__":
    main()
