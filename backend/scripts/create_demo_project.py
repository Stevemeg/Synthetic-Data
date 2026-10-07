"""Development-only generated fake clinical cohort; each invocation creates an isolated demo."""

import hashlib
import json

from backend.scripts.evaluation_smoke_test import poll
from backend.scripts.platform_smoke_test import main
from backend.tests.evaluation_fixture import evaluation_fixture


def workflow(client, start_worker):
    raw = evaluation_fixture().to_csv(index=False, lineterminator="\n").encode()
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Cardio Readmission Research",
            "description": "Development demo · Programmatically generated fake data only. No hospital data or clinical relationships.",
        },
    )
    response.raise_for_status()
    project = response.json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        data={
            "name": "Synthetic Clinical Cohort · Demo synthetic source fixture",
            "modality": "tabular",
        },
        files={"file": ("demo-synthetic-clinical-cohort.csv", raw, "text/csv")},
    )
    response.raise_for_status()
    dataset = response.json()
    assert dataset["sha256"] == hashlib.sha256(raw).hexdigest()
    preflight = client.post(f"/api/v1/datasets/{dataset['id']}/tabular/preflight")
    preflight.raise_for_status()
    assert preflight.json()["compatible"]
    overrides = {
        "age_group": {"annotations": ["QUASI_IDENTIFIER"]},
        "sex": {"annotations": ["QUASI_IDENTIFIER"]},
        "diagnosis_group": {"annotations": ["SENSITIVE_ATTRIBUTE"]},
    }
    response = client.put(
        f"/api/v1/datasets/{dataset['id']}/tabular/governance", json={"overrides": overrides}
    )
    response.raise_for_status()
    response = client.post(
        f"/api/v1/projects/{project['id']}/jobs",
        json={
            "modality": "tabular",
            "dataset_id": dataset["id"],
            "engine": "gaussian_copula",
            "requested_samples": 400,
            "random_seed": 42,
            "configuration": {"holdout_fraction": 0.2, "split_seed": 42},
            "metadata_overrides": overrides,
        },
        headers={"Idempotency-Key": "demo-gaussian-copula"},
    )
    response.raise_for_status()
    start_worker()
    job = poll(client, f"/api/v1/jobs/{response.json()['id']}")
    response = client.post(
        f"/api/v1/projects/{project['id']}/release-policies",
        json={
            "name": "Illustrative Research Demo Policy",
            "version": 1,
            "description": "Example operational thresholds for demonstration only. Not a medical, legal, regulatory or privacy standard.",
            "illustrative": True,
            "rules": {
                "structural_validation": {"equals": True},
                "holdout_column_shapes": {"minimum": 0.8},
                "exact_training_match_fraction": {"maximum": 0.01},
                "dcr_overfitting_protection": {"minimum": 0.7},
                "tstr_trtr_ratio": {"minimum": 0.85},
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
            "random_seed": 42,
            "privacy": {
                "known_columns": ["age_group", "sex"],
                "sensitive_columns": ["diagnosis_group"],
            },
            "utility": {"target": "readmitted", "task": "BINARY_CLASSIFICATION"},
            "release_policy_id": policy["id"],
        },
    )
    response.raise_for_status()
    evaluation = poll(client, f"/api/v1/evaluations/{response.json()['id']}")
    response = client.post(f"/api/v1/evaluations/{evaluation['id']}/governance-report")
    response.raise_for_status()
    report = response.json()
    download = client.get(f"/api/v1/artifacts/{report['id']}/download")
    download.raise_for_status()
    assert len(download.content) == report["size_bytes"]
    assert hashlib.sha256(download.content).hexdigest() == report["sha256"]
    assert "Warnings and limitations" in download.text and "Provenance" in download.text
    assert "&gt;= 0.8; Required" in download.text
    assert "&lt;= 0.01; Required" in download.text
    assert ">= None" not in download.text and "&gt;= None" not in download.text
    assert "storage_key" not in download.text and "source_path" not in download.text
    assert raw.decode().splitlines()[1] not in download.text
    for claim in (
        "HIPAA compliant",
        "GDPR compliant",
        "100% anonymous",
        "zero privacy risk",
        "safe to share",
        "re-identification impossible",
    ):
        assert claim.lower() not in download.text.lower()
    artifacts = (
        client.get(f"/api/v1/jobs/{job['id']}/artifacts").json()["items"]
        + client.get(f"/api/v1/evaluations/{evaluation['id']}/reports").json()["items"]
    )
    job["evaluation_run_id"] = evaluation["id"]
    job["governance_report_id"] = report["id"]
    print(
        json.dumps(
            {
                "demo": "Generated fake data only",
                "project_id": project["id"],
                "dataset_id": dataset["id"],
                "generation_job_id": job["id"],
                "evaluation_id": evaluation["id"],
                "report": report,
                "decision": evaluation["result_summary_json"]["release"]["decision"],
                "hash_verification": "PASS",
            }
        ),
        flush=True,
    )
    return project, dataset, job, artifacts


def restart_check(client, job):
    response = client.get(f"/api/v1/evaluations/{job['evaluation_run_id']}")
    response.raise_for_status()
    assert response.json()["status"] == "SUCCEEDED"
    report = client.get(f"/api/v1/artifacts/{job['governance_report_id']}").json()
    content = client.get(f"/api/v1/artifacts/{report['id']}/download").content
    assert hashlib.sha256(content).hexdigest() == report["sha256"]


if __name__ == "__main__":
    main(workflow, restart_check)
