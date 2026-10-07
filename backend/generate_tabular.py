"""Disabled legacy placeholder; source-row resampling is not synthesis."""

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.core.errors import UnavailableError


def generate_tabular_data(input_file, output_file, num_rows):
    raise UnavailableError(
        "Use the registered-dataset Phase 3 tabular job API; this legacy placeholder stays disabled and row resampling is absent."
    )


def main():
    parser = argparse.ArgumentParser(description="Unavailable: legacy tabular placeholder removed.")
    parser.add_argument("--input_file", required=True)
    parser.add_argument("--output_file", required=True)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--dataset_type")
    args = parser.parse_args()
    try:
        generate_tabular_data(args.input_file, args.output_file, args.rows)
    except UnavailableError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
