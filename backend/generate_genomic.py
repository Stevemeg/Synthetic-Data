"""Disabled legacy placeholder; random arrays are not genomic synthesis."""

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.core.errors import UnavailableError


def generate_genomic_data(input_file, output_file, num_sequences):
    raise UnavailableError(
        "Genomics is Experimental / Not available in production workflow. No synthesis engine is implemented."
    )


def main():
    parser = argparse.ArgumentParser(description="Unavailable: random genomic placeholder removed.")
    parser.add_argument("--input_file", required=True)
    parser.add_argument("--output_file", required=True)
    parser.add_argument("--count", type=int, required=True)
    args = parser.parse_args()
    try:
        generate_genomic_data(args.input_file, args.output_file, args.count)
    except UnavailableError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
