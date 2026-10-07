"""Real PostgreSQL + child-process synthesis, including failure boundaries."""

import hashlib
import io
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier
from time import monotonic, sleep
from uuid import UUID

import pandas as pd
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from backend.app import create_app
from backend.app.config import ROOT
from backend.app.core.errors import AppError
from backend.app.db.models import Artifact, AuditEvent, Dataset, GenerationJob
from backend.app.db.repositories.jobs import JobClaim, QueueRepository, utcnow
from backend.app.db.session import Database
from backend.app.storage.local import LocalArtifactStore
from backend.app.workers.runner import Worker
from backend.tests.tabular_fixture import clinical_fixture
from backend.tests.test_platform_integration import dataset, project

pytestmark = pytest.mark.integration


def queued_tabular(client, count=25, **options):
    pid = project(client)
    raw = clinical_fixture().to_csv(index=False, lineterminator="\n").encode()
    data = dataset(client, pid, raw, "tabular")
    analysis = client.post(f"/api/v1/datasets/{data['id']}/tabular/preflight")
    assert analysis.status_code == 200 and analysis.json()["compatible"], analysis.text
    assert "SOURCE-" not in analysis.text and "Invented private" not in analysis.text
    body = {
        "modality": "tabular",
        "dataset_id": data["id"],
        "requested_samples": count,
        "random_seed": 42,
        **options,
    }
    response = client.post(f"/api/v1/projects/{pid}/jobs", json=body)
    assert response.status_code == 202, response.text
    return data, response.json(), raw


def verify_output(client, database, store, data, item, raw):
    result = client.get(f"/api/v1/jobs/{item['id']}").json()
    assert result["status"] == "SUCCEEDED", result
    assert result["produced_samples"] == result["requested_samples"]
    artifacts = client.get(f"/api/v1/jobs/{item['id']}/artifacts").json()["items"]
    assert len(artifacts) == 4
    assert {a["artifact_type"] for a in artifacts} == {
        "SYNTHESIS_MODEL",
        "SYNTHETIC_DATASET",
        "STRUCTURAL_VALIDATION_REPORT",
        "RUN_METADATA",
    }
    manifest = None
    for a in artifacts:
        assert "storage_key" not in a
        with database.sessions() as session:
            persisted = session.get(Artifact, UUID(a["id"]))
        info = store.metadata(persisted.storage_key)
        assert info.sha256 == a["sha256"] and info.size_bytes == a["size_bytes"]
        response = client.get(f"/api/v1/artifacts/{a['id']}/download")
        if a["artifact_type"] == "SYNTHESIS_MODEL":
            assert response.status_code == 403 and not a["downloadable"]
            assert persisted.metadata_json["engine"] == item["engine"]
            assert persisted.metadata_json["source_sha256"] == data["sha256"]
            assert persisted.metadata_json["training_row_count"] == 80
        else:
            assert response.status_code == 200, response.text
            assert hashlib.sha256(response.content).hexdigest() == a["sha256"]
            if a["artifact_type"] == "SYNTHETIC_DATASET":
                generated = pd.read_csv(io.BytesIO(response.content))
                assert len(generated) == item["requested_samples"]
                assert (
                    generated.patient_id.is_unique
                    and generated.patient_id.str.startswith("SYN-").all()
                )
                assert not set(generated.patient_id) & set(clinical_fixture().patient_id)
                assert list(generated.columns) == [
                    c for c in clinical_fixture().columns if c != "clinical_notes"
                ]
                assert "Unnamed: 0" not in generated
            elif a["artifact_type"] == "STRUCTURAL_VALIDATION_REPORT":
                assert response.json()["passed"]
            else:
                manifest = response.json()
    assert manifest["source_dataset_sha256"] == hashlib.sha256(raw).hexdigest()
    assert manifest["tabular"]["split"]["training_row_count"] == 80
    assert manifest["tabular"]["split"]["holdout_row_count"] == 20
    assert manifest["tabular"]["structural_validation"]["passed"]
    assert manifest["runtime_versions"]["sdv"] == "1.25.0"
    assert len(manifest["model"]["sha256"]) == 64 and manifest["model"]["artifact_id"]
    assert "SOURCE-" not in str(manifest) and "Invented private" not in str(manifest)
    with database.sessions() as session:
        source = session.get(Dataset, UUID(data["id"]))
        events = set(
            session.scalars(
                select(AuditEvent.event_type).where(AuditEvent.entity_id == UUID(item["id"]))
            )
        )
    assert events >= {
        "TABULAR_JOB_SUBMITTED",
        "TABULAR_TRAINING_STARTED",
        "TABULAR_SAMPLING_COMPLETED",
        "TABULAR_VALIDATION_COMPLETED",
        "TABULAR_MODEL_CREATED",
        "TABULAR_JOB_SUCCEEDED",
    }
    with store.get(source.storage_key) as stream:
        assert stream.read() == raw
    return manifest, artifacts


@pytest.mark.model
def test_real_tabular_e2e_two_workers_restart_and_integrity(pg_settings):
    database = Database(pg_settings)
    store = LocalArtifactStore(pg_settings.artifact_storage_path)
    try:
        with TestClient(create_app(pg_settings)) as client:
            data, item, raw = queued_tabular(
                client,
                metadata_overrides={
                    "age": {"annotations": ["QUASI_IDENTIFIER"]},
                    "lab_value": {"annotations": ["SENSITIVE_ATTRIBUTE"]},
                },
                validation_rules={"age": {"numeric_min": 0, "numeric_max": 120}},
            )
        barrier = Barrier(2)

        def run(index):
            worker = Worker(pg_settings, database, store, f"tabular-worker-{index}")
            barrier.wait()
            return worker.run_once()

        with ThreadPoolExecutor(2) as pool:
            assert sum(pool.map(run, range(2))) == 1
        with TestClient(create_app(pg_settings)) as restarted:
            manifest, artifacts = verify_output(restarted, database, store, data, item, raw)
            job = restarted.get(f"/api/v1/jobs/{item['id']}").json()
            assert job["attempt_count"] == 1
            assert manifest["configuration"]["metadata_overrides"]["age"]["annotations"] == [
                "QUASI_IDENTIFIER"
            ]
            output = next(a for a in artifacts if a["artifact_type"] == "SYNTHETIC_DATASET")
            with database.sessions() as session:
                persisted = session.get(Artifact, UUID(output["id"]))
            store.path(persisted.storage_key).write_bytes(b"tampered")
            assert restarted.get(f"/api/v1/artifacts/{output['id']}/download").status_code == 503
    finally:
        database.dispose()


@pytest.mark.model
def test_retry_publication_failure_compensation_and_new_claim(pg_client, pg_settings, monkeypatch):
    data, item, raw = queued_tabular(pg_client)
    database = Database(pg_settings)
    store = LocalArtifactStore(pg_settings.artifact_storage_path)
    real_put = store.put

    def fail_model(key, source):
        if key.endswith("synthesizer.pkl"):
            raise OSError("Controlled temporary storage outage")
        return real_put(key, source)

    worker = Worker(pg_settings, database, store)
    try:
        monkeypatch.setattr(store, "put", fail_model)
        assert worker.run_once()
        first = pg_client.get(f"/api/v1/jobs/{item['id']}").json()
        assert first["status"] == "QUEUED" and first["attempt_count"] == 1
        assert first["error_code"] == "TRANSIENT_IO_ERROR"
        assert pg_client.get(f"/api/v1/jobs/{item['id']}/artifacts").json()["items"] == []
        assert not list(store.root.rglob("dataset.csv"))
        with database.sessions() as session:
            old_token = session.get(GenerationJob, UUID(item["id"])).claim_token
        with database.engine.begin() as connection:
            connection.execute(
                update(GenerationJob)
                .where(GenerationJob.id == UUID(item["id"]))
                .values(available_at=utcnow() - timedelta(seconds=1))
            )
        monkeypatch.setattr(store, "put", real_put)
        assert worker.run_once()
        verify_output(pg_client, database, store, data, item, raw)
        with database.sessions() as session:
            result = session.get(GenerationJob, UUID(item["id"]))
        assert result.attempt_count == 2 and result.claim_token != old_token
    finally:
        database.dispose()


def test_source_integrity_submission_and_before_fit(pg_client, pg_settings, tmp_path):
    data, item, _ = queued_tabular(pg_client)
    database = Database(pg_settings)
    store = LocalArtifactStore(pg_settings.artifact_storage_path)
    try:
        with database.sessions() as session:
            registered = session.get(Dataset, UUID(data["id"]))
        store.path(registered.storage_key).write_bytes(b"mutated")
        assert (
            pg_client.post(f"/api/v1/datasets/{data['id']}/tabular/preflight").json()["error"][
                "code"
            ]
            == "SOURCE_ARTIFACT_INTEGRITY_FAILED"
        )
        response = pg_client.post(
            f"/api/v1/projects/{item['project_id']}/jobs",
            json={"modality": "tabular", "dataset_id": data["id"], "requested_samples": 1},
        )
        assert response.json()["error"]["code"] == "SOURCE_ARTIFACT_INTEGRITY_FAILED"
        assert Worker(pg_settings, database, store).run_once()
        result = pg_client.get(f"/api/v1/jobs/{item['id']}").json()
        assert result["status"] == "FAILED" and result["attempt_count"] == 1
        assert result["error_code"] == "SOURCE_ARTIFACT_INTEGRITY_FAILED"
        assert not pg_client.get(f"/api/v1/jobs/{item['id']}/artifacts").json()["items"]
    finally:
        database.dispose()


def test_bad_metadata_not_queued_or_retried(pg_client):
    data, item, _ = queued_tabular(pg_client)
    for overrides in (
        {"unknown": {"role": "MODELLED"}},
        {"clinical_notes": {"role": "MODELLED"}},
        {"patient_id": {"role": "IDENTIFIER", "unique": False}},
    ):
        response = pg_client.post(
            f"/api/v1/projects/{item['project_id']}/jobs",
            json={
                "modality": "tabular",
                "dataset_id": data["id"],
                "requested_samples": 1,
                "metadata_overrides": overrides,
            },
        )
        assert response.status_code == 400
    assert pg_client.get(f"/api/v1/projects/{item['project_id']}/jobs").json()["total"] == 1


def test_phase3_migration_downgrade_upgrade_and_drift(pg_settings):
    database = Database(pg_settings)
    config = Config(str(ROOT / "alembic.ini"))
    try:
        with database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0001_platform")
            command.upgrade(config, "head")
            command.check(config)
        database.ready()
    finally:
        database.dispose()


def test_timeout_terminates_child_without_publication(pg_settings):
    settings = replace(pg_settings, tabular_job_timeout_seconds=1)
    database = Database(settings)
    try:
        with TestClient(create_app(settings)) as client:
            _, item, _ = queued_tabular(client)
            assert Worker(
                settings, database, LocalArtifactStore(settings.artifact_storage_path)
            ).run_once()
            result = client.get(f"/api/v1/jobs/{item['id']}").json()
            assert (
                result["status"] == "FAILED" and result["error_code"] == "TABULAR_TRAINING_TIMEOUT"
            )
            assert client.get(f"/api/v1/jobs/{item['id']}/artifacts").json()["items"] == []
    finally:
        database.dispose()


@pytest.mark.model
def test_required_structural_failure_is_permanent_and_reports_facts(pg_client, pg_settings):
    _, item, _ = queued_tabular(
        pg_client, validation_rules={"sex": {"allowed_values": ["impossible-fixture-value"]}}
    )
    database = Database(pg_settings)
    try:
        worker = Worker(
            pg_settings, database, LocalArtifactStore(pg_settings.artifact_storage_path)
        )
        assert worker.run_once() and not worker.run_once()
        result = pg_client.get(f"/api/v1/jobs/{item['id']}").json()
        assert result["status"] == "FAILED" and result["attempt_count"] == 1
        assert result["error_code"] == "TABULAR_STRUCTURAL_VALIDATION_FAILED"
        assert result["metadata_json"]["structural_validation"]["rule_violations"] == [
            {"column": "sex", "rule": "allowed_values", "count": 25}
        ]
        assert pg_client.get(f"/api/v1/jobs/{item['id']}/artifacts").json()["items"] == []
    finally:
        database.dispose()


def run_worker_process(settings):
    database = Database(settings)
    try:
        Worker(
            settings, database, LocalArtifactStore(settings.artifact_storage_path), "crash-worker"
        ).run_once()
    finally:
        database.dispose()


@pytest.mark.model
def test_actual_worker_death_during_neural_training_and_fenced_recovery(pg_client, pg_settings):
    _, item, _ = queued_tabular(
        pg_client, engine="ctgan", configuration={"epochs": 50, "batch_size": 20}
    )
    database = Database(pg_settings)
    process = multiprocessing.get_context("spawn").Process(
        target=run_worker_process, args=(pg_settings,)
    )
    process.start()
    queue = QueueRepository(database, 60)
    try:
        deadline = monotonic() + 90
        while monotonic() < deadline:
            with database.sessions() as session:
                started = session.scalar(
                    select(AuditEvent.id).where(
                        AuditEvent.entity_id == UUID(item["id"]),
                        AuditEvent.event_type == "TABULAR_TRAINING_STARTED",
                    )
                )
            if started:
                break
            assert process.is_alive()
            sleep(0.05)
        assert started
        process.kill()
        process.join(timeout=10)
        assert not process.is_alive()
        with database.sessions() as session:
            old_job = session.get(GenerationJob, UUID(item["id"]))
            assert old_job.status == "RUNNING"
        # Advance the lease timestamp to exercise expiry without a 60-second sleep.
        with database.engine.begin() as connection:
            connection.execute(
                update(GenerationJob)
                .where(GenerationJob.id == old_job.id)
                .values(lease_expires_at=utcnow() - timedelta(seconds=1))
            )
        claim = queue.claim("recovered")
        assert (
            claim and claim.job.attempt_count == 2 and claim.job.claim_token != old_job.claim_token
        )
        try:
            stale = JobClaim(old_job, claim.connection, claim.key)
            with pytest.raises(AppError):
                queue.heartbeat(stale)
            with pytest.raises(AppError):
                queue.succeed(stale, [], {}, 25, utcnow())
            queue.fail(claim, "CONTROLLED_TEST_STOP", "Recovery verified", False)
        finally:
            claim.release()
        assert pg_client.get(f"/api/v1/jobs/{item['id']}/artifacts").json()["items"] == []
    finally:
        if process.is_alive():
            process.kill()
            process.join(timeout=10)
        database.dispose()
