from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    default_report = root / "report" / "formal_paper_canonical_s42_current"
    parser = argparse.ArgumentParser(
        description="Render thesis/paper figures directly from an experiment report directory."
    )
    parser.add_argument(
        "--report_dir",
        default=str(default_report),
        help="Directory containing report csv/jsonl outputs from evaluate.py.",
    )
    parser.add_argument(
        "--out_dir",
        default=None,
        help="Figure output directory. Defaults to <report_dir>/paper_figures.",
    )
    parser.add_argument(
        "--log_md",
        default=None,
        help="Optional markdown log passed through to the figure generator.",
    )
    return parser.parse_args()


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required report artifact: {path}")


def pick_generator_python(root: Path) -> str:
    candidates = [
        root / ".venv" / "Scripts" / "python.exe",
        Path(sys.executable),
    ]
    probe = "import matplotlib, pandas, numpy; print('ok')"
    for candidate in candidates:
        if not candidate.exists():
            continue
        result = subprocess.run(
            [str(candidate), "-c", probe],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0:
            return str(candidate)
    raise RuntimeError(
        "No Python interpreter with matplotlib/pandas/numpy was found. "
        "Tried repo .venv and current interpreter."
    )


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    report_dir = Path(args.report_dir).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else report_dir / "paper_figures"
    generator = root / "scripts" / "paper_figures" / "generate_ccfa_figures.py"
    generator_python = pick_generator_python(root)

    require_file(report_dir / "metrics_table.csv")
    require_file(report_dir / "task_metrics.csv")
    require_file(report_dir / "error_cases.jsonl")
    require_file(generator)

    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        generator_python,
        str(generator),
        "--data_dir",
        str(report_dir),
        "--out_dir",
        str(out_dir),
    ]
    if args.log_md:
        cmd.extend(["--log_md", str(Path(args.log_md).resolve())])

    subprocess.run(cmd, check=True)
    print(f"paper figures generated -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
