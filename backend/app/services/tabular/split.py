import numpy as np
import pandas as pd

from ...core.errors import AppError
from ...schemas.tabular import TabularConfig


def split_table(frame: pd.DataFrame, config: TabularConfig):
    """PCG64 positional permutation v1; source order preserved inside partitions."""
    if len(frame) < 10:
        raise AppError(
            "At least 10 source rows are required operationally", "TABULAR_DATASET_INVALID"
        )
    warnings = []
    count = int(len(frame) * config.holdout_fraction)
    if len(frame) < 20 and count:
        count = 0
        warnings.append("Holdout disabled below 20 source rows; operational small-table policy")
    if len(frame) - count < 10:
        raise AppError("Split leaves fewer than 10 training rows", "TABULAR_CONFIG_INVALID")
    positions = np.random.Generator(np.random.PCG64(config.split_seed)).permutation(len(frame))
    holdout = np.sort(positions[:count])
    train = np.sort(positions[count:])
    return (
        frame.iloc[train].copy(),
        frame.iloc[holdout].copy(),
        {
            "algorithm": "numpy-pcg64-positional-permutation",
            "algorithm_version": "1",
            "split_seed": config.split_seed,
            "requested_holdout_fraction": config.holdout_fraction,
            "holdout_fraction": count / len(frame),
            "training_row_count": len(train),
            "holdout_row_count": len(holdout),
            "source_row_count": len(frame),
            "warnings": warnings,
        },
    )
