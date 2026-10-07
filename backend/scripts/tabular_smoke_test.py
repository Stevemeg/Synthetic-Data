"""Repeatable real HTTP/API/worker tabular smoke; invented data only."""

import hashlib
import io
import json
from time import monotonic, sleep

import pandas as pd

from backend.scripts.platform_smoke_test import main
from backend.tests.tabular_fixture import clinical_fixture


def workflow(client, start_worker):
    frame = clinical_fixture(100)
    raw = frame.to_csv(index=False, lineterminator="\n").encode()
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Tabular smoke fixture",
            "description": "Invented engineering data; no patient data",
        },
    )
    response.raise_for_status()
    project = response.json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        data={"name": "Invented clinical table", "modality": "tabular"},
        files={"file": ("invented_clinical.csv", raw, "text/csv")},
    )
    response.raise_for_status()
    dataset = response.json()
    assert dataset["sha256"] == hashlib.sha256(raw).hexdigest()
    response = client.post(f"/api/v1/datasets/{dataset['id']}/tabular/preflight")
    response.raise_for_status()
    assert response.json()["compatible"]
    assert "SOURCE-" not in response.text and "Invented private" not in response.text
    body = {
        "modality": "tabular",
        "dataset_id": dataset["id"],
        "engine": "gaussian_copula",
        "requested_samples": 50,
        "random_seed": 42,
        "configuration": {"holdout_fraction": 0.2, "split_seed": 42},
        "metadata_overrides": {"age": {"annotations": ["QUASI_IDENTIFIER"]}},
        "validation_rules": {"age": {"numeric_min": 0, "numeric_max": 120}},
    }
    response = client.post(
        f"/api/v1/projects/{project['id']}/jobs",
        json=body,
        headers={"Idempotency-Key": "tabular-smoke"},
    )
    assert response.status_code == 202, response.text
    job = response.json()
    replay = client.post(
        f"/api/v1/projects/{project['id']}/jobs",
        json=body,
        headers={"Idempotency-Key": "tabular-smoke"},
    )
    assert replay.status_code == 200 and replay.json()["id"] == job["id"]
    start_worker()
    deadline = monotonic() + 120
    while monotonic() < deadline:
        job = client.get(f"/api/v1/jobs/{job['id']}").json()
        if job["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            break
        sleep(0.5)
    assert job["status"] == "SUCCEEDED", {
        key: job.get(key) for key in ("status", "error_code", "attempt_count")
    }
    artifacts = client.get(f"/api/v1/jobs/{job['id']}/artifacts").json()["items"]
    assert len(artifacts) == 4
    manifest = None
    for artifact in artifacts:
        response = client.get(f"/api/v1/artifacts/{artifact['id']}/download")
        if artifact["artifact_type"] == "SYNTHESIS_MODEL":
            assert response.status_code == 403
            continue
        response.raise_for_status()
        assert hashlib.sha256(response.content).hexdigest() == artifact["sha256"]
        if artifact["artifact_type"] == "SYNTHETIC_DATASET":
            generated = pd.read_csv(io.BytesIO(response.content))
            assert len(generated) == 50 and generated.patient_id.is_unique
            assert not set(generated.patient_id) & set(frame.patient_id)
            assert list(generated.columns) == [c for c in frame if c != "clinical_notes"]
        elif artifact["artifact_type"] == "STRUCTURAL_VALIDATION_REPORT":
            assert response.json()["passed"]
        else:
            manifest = response.json()
    assert manifest["source_dataset_sha256"] == dataset["sha256"]
    assert (
        manifest["tabular"]["split"]["training_row_count"] == 80
        and manifest["tabular"]["split"]["holdout_row_count"] == 20
    )
    assert manifest["model"]["sha256"] == next(
        a["sha256"] for a in artifacts if a["artifact_type"] == "SYNTHESIS_MODEL"
    )
    print(
        json.dumps(
            {
                "source_rows": 100,
                "training_rows": 80,
                "holdout_rows": 20,
                "requested_rows": 50,
                "produced_rows": 50,
                "schema": "PASS",
                "identifiers": "PASS",
                "hashes": "PASS",
                "artifacts": [
                    {"id": a["id"], "type": a["artifact_type"], "sha256": a["sha256"]}
                    for a in artifacts
                ],
                "exact_row_diagnostic": manifest["tabular"]["exact_row_diagnostic"],
                "job_state": job["status"],
            }
        ),
        flush=True,
    )
    return project, dataset, job, artifacts


if __name__ == "__main__":
    main(workflow)
