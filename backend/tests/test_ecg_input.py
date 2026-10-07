from dataclasses import replace

import numpy as np
import pytest

from backend.app.core.errors import AppError
from backend.app.utils.ecg_input import extract_segments, read_ecg_csv


def csv(tmp_path, text):
    path = tmp_path / "signals.csv"
    path.write_text(text, encoding="utf-8")
    return path


def row(samples=200, label="original-label"):
    return ",".join([*(str(x) for x in np.linspace(-1, 1, samples)), label]) + "\n"


def test_ecg_csv_schema(tmp_path, settings):
    signals = read_ecg_csv(csv(tmp_path, row()), settings)
    assert signals.shape == (1, 200)
    assert signals.dtype == np.float32


@pytest.mark.parametrize(
    "text",
    [
        "",
        "1,2,label\n",
        row().replace("-1.0", "not-numeric"),
        row().replace("-1.0", "NaN"),
        row().replace("-1.0", "inf"),
        row().replace("-1.0", ""),
        row() + "1,2,x\n",
    ],
)
def test_invalid_ecg_csv(tmp_path, settings, text):
    with pytest.raises(AppError):
        read_ecg_csv(csv(tmp_path, text), settings)


def test_row_limit(tmp_path, settings):
    with pytest.raises(AppError):
        read_ecg_csv(csv(tmp_path, row() * 2), replace(settings, max_source_rows=1))


@pytest.mark.parametrize(
    "peaks", [{}, {"ECG_R_Peaks": []}, {"ECG_R_Peaks": None}, {"ECG_R_Peaks": [0, 199]}]
)
def test_empty_or_boundary_peaks(settings, peaks):
    signals = np.linspace(-1, 1, 200, dtype=np.float32)[None, :]
    with pytest.raises(AppError, match="No valid heartbeat"):
        extract_segments(signals, settings, lambda x, **_: x, lambda x, **_: peaks)


@pytest.mark.parametrize(
    "signals", [np.empty((0, 200)), np.empty((1, 0)), np.array([[np.nan] * 96]), np.zeros((1, 200))]
)
def test_empty_invalid_or_constant_signals(settings, signals):
    with pytest.raises(AppError):
        extract_segments(signals, settings, lambda x, **_: x, lambda x, **_: {"ECG_R_Peaks": [50]})


def test_normalization_and_inclusive_end(settings):
    signals = np.linspace(-5, 7, 96, dtype=np.float32)[None, :]
    segments, skipped = extract_segments(
        signals, settings, lambda x, **_: x, lambda x, **_: {"ECG_R_Peaks": np.array([32])}
    )
    assert segments.shape == (1, 96) and skipped == 0
    assert segments.min() == 0 and segments.max() == 1


def test_preprocessor_errors_are_safe(settings):
    def fail(*args, **kwargs):
        raise ValueError("source data")

    with pytest.raises(AppError, match="No valid heartbeat"):
        extract_segments(np.linspace(0, 1, 200)[None, :], settings, fail, fail)


def test_segment_limit(settings):
    with pytest.raises(AppError, match="Too many"):
        extract_segments(
            np.linspace(0, 1, 200)[None, :],
            replace(settings, max_ecg_segments=1),
            lambda x, **_: x,
            lambda x, **_: {"ECG_R_Peaks": [50, 100]},
        )
