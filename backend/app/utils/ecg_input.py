"""CSV validation and heartbeat extraction independent of PyTorch."""

import logging
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from ..config import Settings
from ..core.errors import AppError, UnavailableError

logger = logging.getLogger(__name__)
SEQUENCE_LENGTH = 96
SAMPLES_BEFORE = 32
SAMPLES_AFTER = 64


def read_ecg_csv(path: Path, settings: Settings) -> np.ndarray:
    if not path.is_file():
        raise AppError("ECG input file does not exist")
    if path.stat().st_size > settings.max_upload_mb * 1024**2:
        raise AppError("ECG input exceeds upload limit", "upload_too_large", 413)
    if path.suffix.lower() != ".csv":
        raise AppError("ECG input must be a .csv file", "invalid_extension")
    try:
        frame = pd.read_csv(path, header=None, nrows=settings.max_source_rows + 1)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeError, ValueError) as exc:
        raise AppError(
            "ECG input must be a nonempty, rectangular UTF-8 CSV", "invalid_ecg"
        ) from exc
    if frame.empty or len(frame) > settings.max_source_rows:
        raise AppError(
            f"ECG input must contain 1 to {settings.max_source_rows} rows", "invalid_ecg"
        )
    # Last column is source label metadata, deliberately excluded from training/export.
    if not SEQUENCE_LENGTH <= frame.shape[1] - 1 <= 10000:
        raise AppError(
            "Each ECG row needs 96 to 10000 signal samples followed by a source label",
            "invalid_ecg",
        )
    if frame.isna().any().any():
        raise AppError("ECG input contains missing fields", "invalid_ecg")
    try:
        signals = frame.iloc[:, :-1].to_numpy(dtype=np.float32)
    except (ValueError, TypeError) as exc:
        raise AppError("ECG signal samples must be numeric", "invalid_ecg") from exc
    if not np.isfinite(signals).all():
        raise AppError("ECG signal samples must be finite", "invalid_ecg")
    return signals


def extract_segments(
    signals: np.ndarray,
    settings: Settings,
    cleaner: Callable | None = None,
    detector: Callable | None = None,
) -> tuple[np.ndarray, int]:
    if (
        signals.ndim != 2
        or len(signals) == 0
        or signals.shape[1] < SEQUENCE_LENGTH
        or not np.isfinite(signals).all()
    ):
        raise AppError("Invalid or empty ECG signal matrix", "invalid_ecg")
    if cleaner is None or detector is None:
        try:
            import neurokit2 as nk
        except ImportError as exc:
            raise UnavailableError(
                "ECG preprocessing dependencies are missing. Install backend/requirements-ml.txt."
            ) from exc
        cleaner = nk.ecg_clean if cleaner is None else cleaner
        detector = nk.ecg_findpeaks if detector is None else detector
    segments = []
    skipped_rows = 0
    for signal in signals:
        row_count = len(segments)
        try:
            if np.ptp(signal) <= 1e-8:
                skipped_rows += 1
                continue
            cleaned = np.asarray(
                cleaner(signal, sampling_rate=settings.ecg_sampling_rate), dtype=np.float32
            )
            if cleaned.shape != signal.shape or not np.isfinite(cleaned).all():
                skipped_rows += 1
                continue
            peaks = detector(cleaned, sampling_rate=settings.ecg_sampling_rate).get(
                "ECG_R_Peaks", []
            )
            if peaks is None or np.asarray(peaks).ndim != 1:
                skipped_rows += 1
                continue
        except Exception:
            # Never log signals or exception text from preprocessing libraries.
            skipped_rows += 1
            continue
        for peak in peaks:
            if not isinstance(peak, (int, np.integer)):
                continue
            start, end = int(peak) - SAMPLES_BEFORE, int(peak) + SAMPLES_AFTER
            if start < 0 or end > len(cleaned):
                continue
            segment = cleaned[start:end]
            spread = np.ptp(segment)
            if spread <= 1e-8:
                continue
            # Sigmoid decoder and training inputs share the [0,1] range.
            segments.append((segment - segment.min()) / spread)
            if len(segments) > settings.max_ecg_segments:
                raise AppError(
                    "Too many extracted ECG segments; reduce the source dataset", "invalid_ecg"
                )
        if len(segments) == row_count:
            skipped_rows += 1
    if not segments:
        raise AppError(
            "No valid heartbeat segments could be extracted. Check signal length and sampling rate.",
            "invalid_ecg",
        )
    logger.info(
        "ecg_preprocessed source_rows=%s segments=%s skipped_rows=%s",
        len(signals),
        len(segments),
        skipped_rows,
    )
    return np.asarray(segments, dtype=np.float32), skipped_rows
