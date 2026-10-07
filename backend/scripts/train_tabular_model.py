"""Preserved offline TVAE training; not wired into the upload API."""

import argparse
import logging
from pathlib import Path

import pandas as pd

from backend.app.core.errors import AppError, UnavailableError

logger = logging.getLogger(__name__)


def train_and_save_model(input_path, model_output_path):
    source, destination = Path(input_path), Path(model_output_path)
    if source.suffix.lower() != ".csv" or not source.is_file():
        raise AppError("An existing CSV dataset is required")
    if destination.exists():
        raise AppError("Model destination exists; choose a new path")
    try:
        data = pd.read_csv(source)
    except (ValueError, pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeError) as exc:
        raise AppError("Malformed CSV dataset") from exc
    if data.empty:
        raise AppError("Dataset is empty")
    if data.isna().any().any():
        raise AppError(
            "Offline TVAE training requires complete input; prepare missing values explicitly"
        )
    try:
        from sdv.metadata import SingleTableMetadata
        from sdv.single_table import TVAESynthesizer
    except ImportError as exc:
        raise UnavailableError(
            "Install backend/requirements-tabular-lab.txt for offline TVAE training"
        ) from exc
    metadata = SingleTableMetadata()
    metadata.detect_from_dataframe(data=data)
    synthesizer = TVAESynthesizer(metadata)
    logger.info("offline_tvae_training_start rows=%s columns=%s", len(data), data.shape[1])
    synthesizer.fit(data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    synthesizer.save(filepath=str(destination))
    logger.info("offline_tvae_training_complete")


def main():
    parser = argparse.ArgumentParser(
        description="Experimental offline TVAE training (no privacy evaluation)."
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--model_path", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        train_and_save_model(args.dataset, args.model_path)
    except AppError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
