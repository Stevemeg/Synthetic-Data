"""Repeatable real FULL evaluation, explicit demo policy and API restart; fake data only."""

import hashlib
import io
import json
from time import monotonic, sleep

import pandas as pd

from backend.scripts.platform_smoke_test import main
from backend.tests.evaluation_fixture import evaluation_fixture


def poll(client, path, seconds=300):
    deadline = monotonic() + seconds
    while monotonic() < deadline:
        response = client.get(path)
        response.raise_for_status()
        result = response.json()
        if result["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            assert result["status"] == "SUCCEEDED", {
                k: result.get(k) for k in ("status", "error_code", "error_message")
            }
            return result
        sleep(0.5)
    raise AssertionError("Smoke workflow did not finish within its deadline")


def workflow(client, start_worker):
    frame = evaluation_fixture()
    raw = frame.to_csv(index=False, lineterminator="\n").encode()
    response = client.post(
        "/api/v1/projects",
        json={"name": "Phase 4 smoke", "description": "Invented engineering data only"},
    )
    response.raise_for_status()
    project = response.json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        data={"name": "Invented evaluation fixture", "modality": "tabular"},
        files={"file": ("invented.csv", raw, "text/csv")},
    )
    response.raise_for_status()
    dataset = response.json()
    assert dataset["sha256"] == hashlib.sha256(raw).hexdigest()
    response = client.post(f"/api/v1/datasets/{dataset['id']}/tabular/preflight")
    response.raise_for_status()
    assert response.json()["compatible"]
    response = client.post(
        f"/api/v1/projects/{project['id']}/jobs",
        json={
            "modality": "tabular",
            "dataset_id": dataset["id"],
            "engine": "gaussian_copula",
            "requested_samples": 400,
            "random_seed": 42,
            "configuration": {"split_seed": 42, "holdout_fraction": 0.2},
            "metadata_overrides": {
                "age_group": {"annotations": ["QUASI_IDENTIFIER"]},
                "sex": {"annotations": ["QUASI_IDENTIFIER"]},
                "diagnosis_group": {"annotations": ["SENSITIVE_ATTRIBUTE"]},
            },
        },
    )
    response.raise_for_status()
    queued = response.json()
    start_worker()
    job = poll(client, f"/api/v1/jobs/{queued['id']}")
    generation_artifacts = client.get(f"/api/v1/jobs/{job['id']}/artifacts").json()["items"]
    synthetic = next(a for a in generation_artifacts if a["artifact_type"] == "SYNTHETIC_DATASET")
    response = client.get(f"/api/v1/artifacts/{synthetic['id']}/download")
    response.raise_for_status()
    assert hashlib.sha256(response.content).hexdigest() == synthetic["sha256"]
    output = pd.read_csv(io.BytesIO(response.content))
    assert len(output) == 400 and output.patient_id.is_unique
    assert not set(output.patient_id) & set(frame.patient_id)
    assert "clinical_notes" not in output and "Unnamed: 0" not in output
    response = client.post(
        f"/api/v1/projects/{project['id']}/release-policies",
        json={
            "name": "Illustrative smoke policy",
            "version": 1,
            "illustrative": True,
            "rules": {
                "structural_validation": {"equals": True},
                "holdout_column_shapes": {"minimum": 0.0},
                "dcr_overfitting_protection": {"minimum": 0.0},
            },
        },
    )
    response.raise_for_status()
    policy = response.json()
    response = client.post(
        f"/api/v1/generation-jobs/{job['id']}/evaluations",
        json={
            "profile": "FULL",
            "group_key": "patient_id",
            "privacy": {
                "known_columns": ["age_group", "sex"],
                "sensitive_columns": ["diagnosis_group"],
            },
            "utility": {"target": "readmitted", "task": "BINARY_CLASSIFICATION"},
            "release_policy_id": policy["id"],
            "random_seed": 42,
        },
    )
    response.raise_for_status()
    evaluation = poll(client, f"/api/v1/evaluations/{response.json()['id']}")
    artifacts = client.get(f"/api/v1/evaluations/{evaluation['id']}/reports").json()["items"]
    assert {a["artifact_type"] for a in artifacts} == {
        "QUALITY_REPORT",
        "PRIVACY_REPORT",
        "UTILITY_REPORT",
        "RELEASE_DECISION",
        "EVALUATION_MANIFEST",
    }
    manifest = None
    for artifact in artifacts:
        response = client.get(f"/api/v1/artifacts/{artifact['id']}/download")
        response.raise_for_status()
        assert hashlib.sha256(response.content).hexdigest() == artifact["sha256"]
        if artifact["artifact_type"] == "EVALUATION_MANIFEST":
            manifest = response.json()
    assert manifest["inputs"]["source"]["sha256"] == dataset["sha256"]
    assert manifest["inputs"]["synthetic"]["sha256"] == synthetic["sha256"]
    assert manifest["source_split"]["training_row_count"] == 320
    assert manifest["source_split"]["holdout_row_count"] == 80
    assert manifest["policy"]["policy_hash"] == policy["policy_hash"]
    summary = evaluation["result_summary_json"]
    assert summary["structural"]["passed"]
    assert summary["release"]["decision"] == "REVIEW_REQUIRED"
    assert not summary["privacy"]["dcr_overfitting_protection"]["methodology"]["gating_eligible"]
    # Verify immutable inputs again after all metric computation/publication.
    response = client.get(f"/api/v1/artifacts/{synthetic['id']}/download")
    assert hashlib.sha256(response.content).hexdigest() == synthetic["sha256"]
    response = client.post(f"/api/v1/datasets/{dataset['id']}/tabular/preflight")
    response.raise_for_status()  # This recalculates the registered source checksum.
    print(
        json.dumps(
            {
                "generation_job_id": job["id"],
                "evaluation_run_id": evaluation["id"],
                "source_sha256": dataset["sha256"],
                "synthetic_sha256": synthetic["sha256"],
                "source_rows": 400,
                "training_rows": 320,
                "holdout_rows": 80,
                "produced_rows": len(output),
                "policy": policy,
                "results": summary,
                "artifacts": [
                    {"id": a["id"], "type": a["artifact_type"], "sha256": a["sha256"]}
                    for a in artifacts
                ],
                "input_and_report_hashes": "PASS",
                "status": evaluation["status"],
            }
        ),
        flush=True,
    )
    job["evaluation_run_id"] = evaluation["id"]
    return project, dataset, job, generation_artifacts + artifacts


def restart_check(client, job):
    result = client.get(f"/api/v1/evaluations/{job['evaluation_run_id']}")
    result.raise_for_status()
    assert result.json()["status"] == "SUCCEEDED"
    assert (
        client.get(f"/api/v1/evaluations/{job['evaluation_run_id']}/reports").json()["total"] == 5
    )


if __name__ == "__main__":
    main(workflow, restart_check)
