import argparse
from pathlib import Path

from backend.app.core.errors import AppError
from backend.app.services.evaluation.visuals import plot_ecg_comparisons


def main():
    parser = argparse.ArgumentParser(
        description="Descriptive ECG plots, not validated quality scores."
    )
    parser.add_argument("--real", required=True, type=Path)
    parser.add_argument("--synthetic", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        plot_ecg_comparisons(args.real, args.synthetic, args.output, args.count, args.seed)
    except AppError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
