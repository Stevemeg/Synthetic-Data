"""Generated engineering relationships only, never a real medical dataset."""

import hashlib
import json

import numpy as np
import pandas as pd

from backend.app.schemas.evaluation import EvaluationCreate
from backend.app.schemas.tabular import TabularConfig
from backend.app.services.evaluation.service import LIMIT_NAMES
from backend.app.services.tabular.profile import (
    canonical_hash,
    model_input,
    read_table,
    resolve_metadata,
)
from backend.app.services.tabular.service import execute
from backend.app.services.tabular.split import split_table
from backend.tests.tabular_fixture import clinical_fixture


def evaluation_fixture(rows=400, duplicated_groups=False):
    frame = clinical_fixture(rows)
    # An invented learnable classification signal, not a medical relationship.
    frame["readmitted"] = ((frame.age > 55) | (frame.diagnosis_group == "C")) ^ (
        np.random.default_rng(73).random(rows) < 0.05
    )
    frame["age_group"] = pd.cut(
        frame.age, [0, 35, 60, 100], labels=["younger", "middle", "older"]
    ).astype(str)
    if duplicated_groups:
        frame["patient_id"] = [f"SOURCE-GROUP-{i // 5:04d}" for i in range(rows)]
    return frame


def real_bundle(root, settings, duplicated_groups=False, holdout_fraction=0.2):
    source_path = root / "source.csv"
    evaluation_fixture(duplicated_groups=duplicated_groups).to_csv(source_path, index=False)
    frame = read_table(source_path, settings)
    columns = resolve_metadata(frame, {}, {})
    config = TabularConfig(holdout_fraction=holdout_fraction)
    training, held, split = split_table(model_input(frame, columns), config)
    metadata = [c.model_dump() for c in columns]
    generation_config = {
        "tabular": config.model_dump(),
        "columns": metadata,
        "metadata_hash": canonical_hash(metadata),
        "split": split,
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "validation_rules": {},
        "warnings": [],
    }
    generation_spec = {
        "engine": "gaussian_copula",
        "source_path": str(source_path),
        "count": 400,
        "seed": 42,
        "token": "a" * 32,
        "configuration": generation_config,
    }
    result = execute(generation_spec, root, settings)
    generated_path = root / "generated" / generation_spec["token"] / "dataset.csv"
    manifest = {
        "job_id": "generation",
        "project_id": "project",
        "dataset_id": "dataset",
        "configuration": generation_config,
        "tabular": result["metadata"]["tabular"],
        "requested_count": 400,
    }
    manifest_path = root / "generation_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    request = EvaluationCreate(
        profile="FULL",
        group_key="patient_id",
        privacy={"known_columns": ["age_group", "sex"], "sensitive_columns": ["diagnosis_group"]},
        utility={"task": "BINARY_CLASSIFICATION", "target": "readmitted"},
    )
    cfg = {
        "request": request.model_dump(mode="json"),
        "policy": None,
        "evaluation_run_id": "evaluation",
        "inputs": {
            name: {
                "id": name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size_bytes": path.stat().st_size,
            }
            for name, path in (
                ("source", source_path),
                ("synthetic", generated_path),
                ("generation_manifest", manifest_path),
            )
        },
        "generation_manifest_hash": canonical_hash(manifest),
        "limits": {name: getattr(settings, name) for name in LIMIT_NAMES},
    }
    spec = {
        "configuration": cfg,
        "source_path": str(source_path),
        "synthetic_path": str(generated_path),
        "manifest_path": str(manifest_path),
        "token": "b" * 32,
        "job_id": "execution",
        "project_id": "project",
        "dataset_id": "dataset",
    }
    return spec, training, held, columns
