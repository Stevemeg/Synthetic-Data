"""Real model execution through PostgreSQL and the dedicated worker boundary."""

import hashlib
import io
from dataclasses import replace
from uuid import UUID
from zipfile import ZipFile

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app import create_app
from backend.app.config import ROOT
from backend.app.db.models import Artifact
from backend.app.db.session import Database
from backend.app.storage.local import LocalArtifactStore
from backend.app.workers.runner import Worker
from backend.tests.test_platform_integration import dataset, job, project

pytestmark = [pytest.mark.integration, pytest.mark.model]


@pytest.fixture(autouse=True)
def small_cpu_runtime(monkeypatch):
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    monkeypatch.setenv("MKL_NUM_THREADS", "1")


def check_outputs(client, job_id, count):
    result = client.get(f"/api/v1/jobs/{job_id}").json()
    assert result["status"] == "SUCCEEDED", result
    assert result["requested_samples"] == result["produced_samples"] == count
    artifacts = client.get(f"/api/v1/jobs/{job_id}/artifacts").json()["items"]
    for artifact in artifacts:
        response = client.get(f"/api/v1/artifacts/{artifact['id']}/download")
        if artifact["artifact_type"] == "MODEL_CHECKPOINT":
            assert response.status_code == 403
            continue
        assert response.status_code == 200, response.text
        assert hashlib.sha256(response.content).hexdigest() == artifact["sha256"]
        assert len(response.content) == artifact["size_bytes"]
        assert "storage_key" not in artifact
        if artifact["artifact_type"] == "RUN_METADATA":
            manifest = response.json()
            assert manifest["job_id"] == job_id
            assert manifest["requested_count"] == manifest["produced_count"] == count
            assert len(manifest["model"]["sha256"]) == 64
        elif artifact["artifact_type"] == "SYNTHETIC_DATASET":
            with np.load(io.BytesIO(response.content), allow_pickle=False) as output:
                assert output["synthetic_sequences"].shape == (count, 96)
                assert "labels" not in output.files
                assert np.isfinite(output["synthetic_sequences"]).all()
                assert output["synthetic_sequences"].min() >= 0
                assert output["synthetic_sequences"].max() <= 1
        elif artifact["artifact_type"] == "IMAGE_ARCHIVE":
            with ZipFile(io.BytesIO(response.content)) as archive:
                assert len(archive.namelist()) == count
    return artifacts


def test_ecg_real_worker_artifacts_restart_and_integrity(pg_settings):
    import neurokit2 as nk

    signal = nk.ecg_simulate(duration=8, sampling_rate=125, random_state=42)
    raw = (",".join(map(str, signal)) + ",ignored-label\n").encode()
    database = Database(pg_settings)
    store = LocalArtifactStore(pg_settings.artifact_storage_path)
    try:
        with TestClient(create_app(pg_settings)) as client:
            pid = project(client)
            data = dataset(client, pid, raw)
            item = job(client, pid, data["id"], "ecg-real").json()
            assert item["status"] == "QUEUED" and item["attempt_count"] == 0
        # Recreate HTTP services while work is still queued, then continue the real workflow.
        with TestClient(create_app(pg_settings)) as client:
            assert client.get(f"/api/v1/jobs/{item['id']}").json()["status"] == "QUEUED"
            worker = Worker(
                replace(pg_settings, ecg_sampling_rate=999, ecg_epochs=2, max_samples=1),
                database,
                store,
            )
            assert worker.run_once() and not worker.run_once()
            artifacts = check_outputs(client, item["id"], 2)
            manifest = client.get(
                f"/api/v1/artifacts/{next(a['id'] for a in artifacts if a['artifact_type'] == 'RUN_METADATA')}/download"
            ).json()
            assert manifest["source_dataset_sha256"] == data["sha256"]
            assert manifest["configuration"]["ecg_sampling_rate"] == 125
            assert manifest["configuration"]["ecg_epochs"] == 1
            assert manifest["runtime_versions"]["torch"]
            with database.sessions() as session:
                checkpoint = session.scalar(
                    select(Artifact).where(
                        Artifact.job_id == UUID(item["id"]),
                        Artifact.artifact_type == "MODEL_CHECKPOINT",
                    )
                )
            import torch

            model = torch.load(store.path(checkpoint.storage_key), weights_only=True)
            assert "model_state" in model and model["seq_len"] == 96
        database.dispose()
        with TestClient(create_app(pg_settings)) as restarted:
            check_outputs(restarted, item["id"], 2)
            output = next(a for a in artifacts if a["artifact_type"] == "SYNTHETIC_DATASET")
            with restarted.app.state.runtime.database.sessions() as session:
                stored = session.get(Artifact, UUID(output["id"]))
            store.path(stored.storage_key).write_bytes(b"tampered-test")
            assert restarted.get(f"/api/v1/artifacts/{output['id']}/download").status_code == 503
    finally:
        database.dispose()


def test_imaging_real_worker_archive_manifest(pg_settings):
    settings = replace(pg_settings, enable_imaging_lab=True, model_dir=ROOT / "backend")
    database = Database(settings)
    try:
        with TestClient(create_app(settings)) as client:
            pid = project(client)
            response = client.post(
                f"/api/v1/projects/{pid}/jobs",
                json={"modality": "imaging", "imaging_modality": "MRI", "requested_samples": 2},
            )
            assert response.status_code == 202, response.text
            item = response.json()
            assert Worker(
                settings, database, LocalArtifactStore(settings.artifact_storage_path)
            ).run_once()
            artifacts = check_outputs(client, item["id"], 2)
            manifest = client.get(
                f"/api/v1/artifacts/{next(a['id'] for a in artifacts if a['artifact_type'] == 'RUN_METADATA')}/download"
            ).json()
            assert manifest["maturity"] == "Experimental"
            assert (
                manifest["dataset_id"] is None
                and manifest["model"]["identifier"] == "generator_brain.pth"
            )
    finally:
        database.dispose()


def test_real_two_workers_execute_one_ecg_job_once(pg_settings):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    import neurokit2 as nk

    signal = nk.ecg_simulate(duration=8, sampling_rate=125, random_state=42)
    raw = (",".join(map(str, signal)) + ",ignored-label\n").encode()
    database = Database(pg_settings)
    store = LocalArtifactStore(pg_settings.artifact_storage_path)
    try:
        with TestClient(create_app(pg_settings)) as client:
            pid = project(client)
            data = dataset(client, pid, raw)
            item = job(client, pid, data["id"]).json()
            barrier = Barrier(2)

            def run(index):
                worker = Worker(pg_settings, database, store, "real-worker-" + str(index))
                barrier.wait()
                return worker.run_once()

            with ThreadPoolExecutor(2) as pool:
                results = list(pool.map(run, range(2)))
            assert sum(results) == 1
            result = client.get(f"/api/v1/jobs/{item['id']}").json()
            assert result["attempt_count"] == 1
            assert len(check_outputs(client, item["id"], 2)) == 3
    finally:
        database.dispose()


def test_real_empty_peak_failure_is_permanent(pg_settings):
    database = Database(pg_settings)
    try:
        with TestClient(create_app(pg_settings)) as client:
            pid = project(client)
            raw = (",".join(["0"] * 400) + ",ignored-label\n").encode()
            data = dataset(client, pid, raw)
            item = job(client, pid, data["id"]).json()
            worker = Worker(
                pg_settings, database, LocalArtifactStore(pg_settings.artifact_storage_path)
            )
            assert worker.run_once()
            assert not worker.run_once()
            result = client.get(f"/api/v1/jobs/{item['id']}").json()
            assert result["status"] == "FAILED" and result["attempt_count"] == 1
            assert result["error_code"] == "DATASET_INVALID"
            assert client.get(f"/api/v1/jobs/{item['id']}/artifacts").json()["items"] == []
    finally:
        database.dispose()
