from pathlib import Path

import numpy as np

from ...core.errors import AppError


def plot_ecg_comparisons(
    real_path: Path, synthetic_path: Path, output_path: Path, count=5, seed=42
):
    """Export descriptive waveform plots; this is not a fidelity/privacy metric."""
    if type(count) is not int or not 1 <= count <= 100:
        raise AppError("Plot count must be between 1 and 100")
    try:
        with np.load(real_path, allow_pickle=False) as real_archive:
            real = real_archive["sequences"]
        with np.load(synthetic_path, allow_pickle=False) as synthetic_archive:
            synthetic = synthetic_archive["synthetic_sequences"]
    except (OSError, KeyError, ValueError) as exc:
        raise AppError("Expected real sequences and synthetic_sequences in NPZ inputs") from exc
    if any(x.ndim != 2 or not len(x) or not np.isfinite(x).all() for x in (real, synthetic)):
        raise AppError("Plot inputs must contain nonempty finite sequence matrices")
    if real.shape[1] != synthetic.shape[1]:
        raise AppError("Real and synthetic sequence dimensions must match")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rng = np.random.default_rng(seed)
    figure, axes = plt.subplots(count, 2, squeeze=False, figsize=(10, 2 * count))
    figure.suptitle("Descriptive waveform comparison (not an evaluation score)")
    for row in range(count):
        axes[row, 0].plot(real[rng.integers(len(real))])
        axes[row, 0].set_title("Source heartbeat window")
        axes[row, 1].plot(synthetic[rng.integers(len(synthetic))])
        axes[row, 1].set_title("Generated unlabeled window")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)
