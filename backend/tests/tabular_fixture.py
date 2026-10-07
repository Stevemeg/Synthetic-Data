"""Invented relationships for engineering tests, with no medical-validity claim."""

import numpy as np
import pandas as pd


def clinical_fixture(rows=100, seed=17):
    rng = np.random.default_rng(seed)
    age = rng.integers(18, 90, rows)
    group = rng.choice(["A", "B", "C"], rows)
    return pd.DataFrame(
        {
            "patient_id": [f"SOURCE-{i:06d}" for i in range(rows)],
            "age": age,
            "sex": rng.choice(["M", "F", "Other"], rows),
            "diagnosis_group": group,
            "lab_value": np.round(age * 0.3 + (group == "C") * 5 + rng.normal(0, 2, rows), 3),
            "admission_date": pd.date_range("2020-01-01", periods=rows).strftime("%Y-%m-%d"),
            "smoker": rng.random(rows) < 0.3,
            "readmitted": rng.random(rows) < np.where(group == "C", 0.5, 0.1),
            "clinical_notes": [f"Invented private free text for fixture {i}" for i in range(rows)],
        }
    )
