"""Real PostgreSQL API, locking, recovery and persistence tests."""

import hashlib
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError

from backend.app import create_app
from backend.app.config import ROOT
from backend.app.core.errors import AppError
from backend.app.db.models import AuditEvent, GenerationJob
from backend.app.db.repositories.jobs import QueueRepository, utcnow
from backend.app.db.session import Database
from backend.app.schemas.platform import JobCreate
from backend.app.services.jobs.failures import JobFailure
from backend.app.services.jobs.service import JobService
from backend.app.storage.local import LocalArtifactStore
from backend.app.workers.runner import Worker

pytestmark = pytest.mark.integration


def project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": "Integration fixture", "description": "Invented non-patient test data"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def dataset(client, pid, raw=None, modality="timeseries"):
    raw = raw or (",".join(str(i % 5) for i in range(400)) + ",ignored-label\n").encode()
    response = client.post(
        f"/api/v1/projects/{pid}/datasets",
        data={"name": "Fixture", "modality": modality},
        files={"file": ("../../test.csv", raw, "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def job(client, pid, did, key=None, count=2):
    response = client.post(
        f"/api/v1/projects/{pid}/jobs",
        json={
            "modality": "timeseries",
            "dataset_id": did,
            "requested_samples": count,
            "random_seed": 42,
        },
        headers={"Idempotency-Key": key} if key else {},
    )
    assert response.status_code in (200, 202), response.text
    return response


def queued(client):
    pid = project(client)
    did = dataset(client, pid)["id"]
    return job(client, pid, did).json()


def test_projects_pagination_readiness(pg_client):
    assert pg_client.get("/ready").json() == {"ready": True}
    pid = project(pg_client)
    assert (
        pg_client.patch(f"/api/v1/projects/{pid}", json={"name": "Updated"}).json()["name"]
        == "Updated"
    )
    page = pg_client.get("/api/v1/projects?limit=1&offset=0").json()
    assert page["total"] == 1 and len(page["items"]) == 1 and page["limit"] == 1
    assert pg_client.get("/api/v1/projects?limit=101").status_code == 422
    assert pg_client.get(f"/api/v1/projects/{uuid4()}").status_code == 404


def test_dataset_sha_and_structural_metadata(pg_client):
    pid = project(pg_client)
    raw = b"age,diagnosis\n20,invented-only\n30,fictional\n"
    data = dataset(pg_client, pid, raw, "tabular")
    assert data["sha256"] == hashlib.sha256(raw).hexdigest()
    assert data["row_count"] == 2 and data["column_count"] == 2
    assert "invented-only" not in str(data["metadata_json"])
    assert "storage_key" not in data
    assert pg_client.get(f"/api/v1/datasets/{data['id']}").status_code == 200
    assert pg_client.get(f"/api/v1/projects/{pid}/datasets").json()["total"] == 1


@pytest.mark.parametrize(
    "filename,mime,raw",
    [
        ("test.exe", "text/csv", b"1,2"),
        ("test.csv", "image/png", b"1,2"),
        ("test.csv", "text/csv", b""),
        ("test.csv", "text/csv", b"x\x00y"),
        ("test.csv", "text/csv", b"1,2,label"),
    ],
)
def test_bad_uploads(pg_client, filename, mime, raw):
    pid = project(pg_client)
    response = pg_client.post(
        f"/api/v1/projects/{pid}/datasets",
        data={"name": "test", "modality": "timeseries"},
        files={"file": (filename, raw, mime)},
    )
    assert response.status_code == 400, response.text
    assert pg_client.get(f"/api/v1/projects/{pid}/datasets").json()["total"] == 0


@pytest.mark.parametrize("modality", ["genomic", "imaging"])
def test_unsupported_engine_no_placeholder(pg_client, modality):
    pid = project(pg_client)
    response = pg_client.post(
        f"/api/v1/projects/{pid}/jobs", json={"modality": modality, "requested_samples": 1}
    )
    assert response.status_code == 501
    assert response.json()["error"]["code"] == "ENGINE_NOT_AVAILABLE"
    assert pg_client.get(f"/api/v1/projects/{pid}/jobs").json()["total"] == 0


def test_idempotency_replay_conflict_project_scope(pg_client):
    pid = project(pg_client)
    did = dataset(pg_client, pid)["id"]
    first = job(pg_client, pid, did, "same")
    second = job(pg_client, pid, did, "same")
    assert first.status_code == 202 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    response = pg_client.post(
        f"/api/v1/projects/{pid}/jobs",
        json={"modality": "timeseries", "dataset_id": did, "requested_samples": 3},
        headers={"Idempotency-Key": "same"},
    )
    assert response.status_code == 409
    other = project(pg_client)
    otherdata = dataset(pg_client, other)["id"]
    assert job(pg_client, other, otherdata, "same").json()["id"] != first.json()["id"]


def test_concurrent_idempotent_submission(pg_client, pg_settings):
    pid = UUID(project(pg_client))
    did = UUID(dataset(pg_client, str(pid))["id"])
    database = Database(pg_settings)
    barrier = Barrier(2)

    def submit():
        with database.sessions() as session:
            barrier.wait()
            item, created = JobService(session, pg_settings).create(
                pid,
                JobCreate(modality="timeseries", dataset_id=did, requested_samples=1),
                "concurrent",
            )
            return item.id, created

    try:
        with ThreadPoolExecutor(2) as executor:
            results = list(executor.map(lambda _: submit(), range(2)))
        assert results[0][0] == results[1][0]
        assert sum(created for _, created in results) == 1
    finally:
        database.dispose()


def test_two_workers_one_job_atomic_claim(pg_client, pg_settings):
    item = queued(pg_client)
    database = Database(pg_settings)
    queue = QueueRepository(database, 60)
    barrier = Barrier(2)

    def claim(worker):
        barrier.wait()
        return queue.claim(worker)

    with ThreadPoolExecutor(2) as executor:
        claims = list(executor.map(claim, ["worker-one", "worker-two"]))
    owners = [claim for claim in claims if claim is not None]
    assert len(owners) == 1
    owner = owners[0]
    try:
        assert str(owner.job.id) == item["id"] and owner.job.attempt_count == 1
        assert queue.claim("worker-three") is None
        queue.fail(owner, "BAD_FIXTURE", "Invalid fixture", False)
        with pytest.raises(AppError):
            queue.succeed(owner, [], {}, 2, utcnow())
        assert pg_client.get(f"/api/v1/jobs/{item['id']}").json()["status"] == "FAILED"
    finally:
        owner.release()
        database.dispose()


def test_lease_recovery_fencing_and_live_owner(pg_client, pg_settings):
    item = queued(pg_client)
    database = Database(pg_settings)
    queue = QueueRepository(database, 60)
    first = queue.claim("first")
    with database.engine.begin() as connection:
        connection.execute(
            update(GenerationJob)
            .where(GenerationJob.id == first.job.id)
            .values(lease_expires_at=utcnow() - timedelta(seconds=1))
        )
    assert queue.claim("second") is None  # advisory ownership survives an expired lease
    old_token = first.job.claim_token
    first.release()
    second = queue.claim("second")
    try:
        assert second.job.attempt_count == 2 and second.job.claim_token != old_token
        fake = type(second)(first.job, second.connection, second.key)
        with pytest.raises(AppError):
            queue.heartbeat(fake)
        queue.fail(second, "INVALID_DATASET", "Permanent invalid input", False)
        assert pg_client.get(f"/api/v1/jobs/{item['id']}").json()["status"] == "FAILED"
    finally:
        second.release()
        database.dispose()


def test_retry_limits_and_cancel(pg_client, pg_settings):
    item = queued(pg_client)
    database = Database(pg_settings)
    queue = QueueRepository(database, 60)
    for attempt in range(1, pg_settings.job_max_attempts + 1):
        claim = queue.claim("retry")
        assert claim.job.attempt_count == attempt
        queue.fail(claim, "STORAGE_UNAVAILABLE", "Transient storage failure", True)
        claim.release()
        with database.engine.begin() as connection:
            connection.execute(
                update(GenerationJob)
                .where(GenerationJob.id == UUID(item["id"]))
                .values(available_at=utcnow() - timedelta(seconds=1))
            )
    result = pg_client.get(f"/api/v1/jobs/{item['id']}").json()
    assert result["status"] == "FAILED" and result["attempt_count"] == pg_settings.job_max_attempts
    assert pg_client.post(f"/api/v1/jobs/{item['id']}/retry").status_code == 409
    cancelled = queued(pg_client)
    assert pg_client.post(f"/api/v1/jobs/{cancelled['id']}/cancel").json()["status"] == "CANCELLED"
    assert queue.claim("other") is None
    database.dispose()


def test_worker_persists_permanent_failure(pg_client, pg_settings, monkeypatch):
    item = queued(pg_client)
    database = Database(pg_settings)
    worker = Worker(pg_settings, database, LocalArtifactStore(pg_settings.artifact_storage_path))
    monkeypatch.setattr(
        worker, "_compute", lambda *args: JobFailure("DATASET_INVALID", "Invalid dataset", False)
    )
    assert worker.run_once()
    assert not worker.run_once()
    result = pg_client.get(f"/api/v1/jobs/{item['id']}").json()
    assert result["status"] == "FAILED" and result["attempt_count"] == 1
    database.dispose()


def test_db_constraints_and_immutable_audit(pg_client, pg_settings):
    item = queued(pg_client)
    database = Database(pg_settings)
    for statement in [
        update(GenerationJob)
        .where(GenerationJob.id == UUID(item["id"]))
        .values(requested_samples=-1),
        update(GenerationJob)
        .where(GenerationJob.id == UUID(item["id"]))
        .values(status="SUCCEEDED"),
        update(AuditEvent).values(actor="system"),
    ]:
        with pytest.raises(IntegrityError), database.engine.begin() as connection:
            connection.execute(statement)
    database.dispose()


def test_restart_persistence(pg_settings):
    with TestClient(create_app(pg_settings)) as first:
        item = queued(first)
    with TestClient(create_app(pg_settings)) as restarted:
        assert restarted.get(f"/api/v1/projects/{item['project_id']}").status_code == 200
        assert restarted.get(f"/api/v1/datasets/{item['dataset_id']}").status_code == 200
        assert restarted.get(f"/api/v1/jobs/{item['id']}").json()["status"] == "QUEUED"


def test_migration_downgrade_upgrade(pg_settings):
    database = Database(pg_settings)
    config = Config(str(ROOT / "alembic.ini"))
    with database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        command.upgrade(config, "head")
    database.ready()
    with database.engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM projects")) == 0
    database.dispose()


def test_cross_project_archived_and_bad_imaging_configuration(pg_client, pg_settings):
    pid = project(pg_client)
    did = dataset(pg_client, pid)["id"]
    other = project(pg_client)
    response = pg_client.post(
        f"/api/v1/projects/{other}/jobs",
        json={"modality": "timeseries", "dataset_id": did, "requested_samples": 1},
    )
    assert response.status_code == 400 and response.json()["error"]["code"] == "DATASET_MISMATCH"
    assert (
        pg_client.patch(f"/api/v1/projects/{pid}", json={"status": "ARCHIVED"}).status_code == 200
    )
    response = pg_client.post(
        f"/api/v1/projects/{pid}/jobs",
        json={"modality": "timeseries", "dataset_id": did, "requested_samples": 1},
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "PROJECT_ARCHIVED"
    for payload in [
        {"modality": "imaging", "imaging_modality": "CT", "requested_samples": 1},
        {"modality": "imaging", "imaging_modality": "MRI", "requested_samples": True},
        {"modality": "timeseries", "requested_samples": 1, "unused": 1},
    ]:
        assert pg_client.post(f"/api/v1/projects/{other}/jobs", json=payload).status_code == 422


def test_expired_last_attempt_becomes_failed(pg_client, pg_settings):
    item = queued(pg_client)
    database = Database(pg_settings)
    queue = QueueRepository(database, 60)
    with database.engine.begin() as connection:
        connection.execute(
            update(GenerationJob).where(GenerationJob.id == UUID(item["id"])).values(max_attempts=1)
        )
    claim = queue.claim("lost")
    claim.release()
    with database.engine.begin() as connection:
        connection.execute(
            update(GenerationJob)
            .where(GenerationJob.id == UUID(item["id"]))
            .values(lease_expires_at=utcnow() - timedelta(seconds=1))
        )
    assert queue.claim("recovery") is None
    result = pg_client.get(f"/api/v1/jobs/{item['id']}").json()
    assert result["status"] == "FAILED" and result["error_code"] == "WORKER_LOST"
    database.dispose()


def test_public_artifact_bounds_and_missing_records(pg_client):
    assert pg_client.get(f"/api/v1/artifacts/{uuid4()}/download").status_code == 404
    assert pg_client.get(f"/api/v1/jobs/{uuid4()}/artifacts").status_code == 404
    item = queued(pg_client)
    assert pg_client.get(f"/api/v1/jobs/{item['id']}/artifacts?limit=101").status_code == 422
    assert pg_client.get(f"/api/v1/jobs/{item['id']}/artifacts").json()["items"] == []


def test_dataset_compensation_on_failed_commit(pg_client, pg_settings, monkeypatch):
    from backend.app.db.repositories.catalog import DatasetRepository
    from backend.app.services.datasets.service import CsvUpload, DatasetService

    pid = UUID(project(pg_client))
    database = Database(pg_settings)
    store = LocalArtifactStore(pg_settings.artifact_storage_path)

    def fail(*args):
        raise RuntimeError("Test insertion failure")

    monkeypatch.setattr(DatasetRepository, "add", fail)
    with database.sessions() as session, pytest.raises(RuntimeError):
        DatasetService(session, store, pg_settings).register(
            pid, "Test", "tabular", CsvUpload("test.csv", "text/csv", io.BytesIO(b"a,b\n1,2\n"))
        )
    assert not list(store.root.rglob("source.csv"))
    database.dispose()
