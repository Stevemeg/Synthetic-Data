"""Fail closed: the old classifier evaluation relied on unjustified source labels."""

import argparse
from pathlib import Path

from backend.app.core.errors import UnavailableError


def run_final_evaluation(synthetic_path: Path, real_test_path: Path):
    raise UnavailableError(
        "Supervised ECG ML utility evaluation is unsupported: the unconditional generator "
        "does not produce justified diagnostic labels. The previous copied-label accuracy "
        "report was invalid. A label-aware generator and independent evaluation design are required."
    )


def main():
    parser = argparse.ArgumentParser(description="Unsupported supervised ECG utility evaluation.")
    parser.add_argument("--synthetic", required=True, type=Path)
    parser.add_argument("--real-test", required=True, type=Path)
    args = parser.parse_args()
    try:
        run_final_evaluation(args.synthetic, args.real_test)
    except UnavailableError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
