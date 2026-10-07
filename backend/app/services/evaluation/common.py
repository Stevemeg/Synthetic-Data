import math
from importlib.metadata import version

import numpy as np
import pandas as pd


def json_safe(value):
    """Portable JSON: unavailable/nonfinite values are null, never NaN or fake scores."""
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    if value is pd.NA or value is pd.NaT:
        return None
    return value


def metric(value=None, status="NOT_APPLICABLE", warnings=None, **details):
    return json_safe(
        {"score": value, "applicability": status, "warnings": warnings or [], **details}
    )


def metadata_for(columns):
    fields = {}
    for c in columns:
        if c.role != "MODELLED":
            continue
        fields[c.name] = {"sdtype": c.semantic_type}
        if c.semantic_type == "datetime" and c.datetime_format:
            fields[c.name]["datetime_format"] = c.datetime_format
    return {"tables": {"clinical": {"columns": fields}}, "relationships": []}


def runtime_versions():
    return {name: version(name) for name in ("sdmetrics", "scikit-learn", "numpy", "pandas", "sdv")}


def bounded_sample(frame, count, seed):
    if len(frame) <= count:
        return frame.copy()
    return frame.sample(n=count, random_state=seed % 4294967296).sort_index().copy()
