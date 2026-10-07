"""Mandatory when MEDSYNTH_S3_TEST=1; exercises actual MinIO, no local fallback."""

import hashlib
import io
import os
from dataclasses import replace
from uuid import UUID, uuid4

import httpx
import pytest
from botocore.exceptions import ClientError
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.app.config import ROOT
from backend.app.db.models import Dataset, Project
from backend.app.db.session import Database
from backend.app.storage.local import LocalArtifactStore
from backend.app.storage.s3 import S3ArtifactStore
from backend.app.workers.runner import Worker
from backend.scripts.migrate_artifacts_to_s3 import migrate
from backend.tests.test_evaluation_integration import generate, submit
from backend.tests.test_platform_integration import dataset, project

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("MEDSYNTH_S3_TEST") != "1",
        reason="Set MEDSYNTH_S3_TEST=1 with local MinIO running",
    ),
]


@pytest.fixture
def s3_platform(pg_settings):
    env = {**dotenv_values(ROOT / ".env"), **os.environ}
    settings = replace(
        pg_settings,
        artifact_storage_backend="s3",
        s3_endpoint=env.get("S3_TEST_ENDPOINT", "http://127.0.0.1:9000"),
        s3_access_key=env["S3_ACCESS_KEY"],
        s3_secret_key=env["S3_SECRET_KEY"],
        s3_bucket="ms-test-" + uuid4().hex,
    )
    store = S3ArtifactStore(settings)
    store.client.create_bucket(Bucket=settings.s3_bucket)
    database = Database(settings)
    try:
        yield settings, store, database
    finally:
        # Only this newly-created isolated test bucket, never the development bucket.
        for page in store.client.get_paginator("list_objects_v2").paginate(
            Bucket=settings.s3_bucket
        ):
            for obj in page.get("Contents", []):
                store.delete(obj["Key"])
        store.client.delete_bucket(Bucket=settings.s3_bucket)
        database.dispose()


def test_s3_integrity_private_immutable_and_source_migration(s3_platform, tmp_path):
    settings, remote, database = s3_platform
    raw = b"programmatically generated fixture only\n"
    info = remote.put("test/immutable.txt", io.BytesIO(raw))
    assert info.sha256 == hashlib.sha256(raw).hexdigest()
    assert remote.metadata("test/immutable.txt") == info
    with pytest.raises(ClientError):
        remote.put("test/immutable.txt", io.BytesIO(b"replacement"))
    assert (
        httpx.get(f"{settings.s3_endpoint}/{settings.s3_bucket}/test/immutable.txt").status_code
        == 403
    )
    local_settings = replace(settings, artifact_storage_backend="local")
    with TestClient(create_app(local_settings)) as client:
        pid = project(client)
        registered = dataset(client, pid)
    local = LocalArtifactStore(settings.artifact_storage_path)
    journal = tmp_path / "rollback.jsonl"
    assert migrate(database, local, remote, journal) == 1
    assert migrate(database, local, remote, journal) == 0
    with database.sessions() as session:
        record = session.get(Dataset, UUID(registered["id"]))
        assert record.storage_key.startswith("s3/")
        assert remote.metadata(record.storage_key).sha256 == registered["sha256"]
    assert journal.read_text(encoding="utf-8").count("\n") == 1
    # Original local backup bytes must not resurrect a logically deleted project.
    with database.sessions.begin() as session:
        record = session.get(Dataset, UUID(registered["id"]))
        key = record.storage_key
        record.storage_key = key.removeprefix("s3/")
        session.get(Project, record.project_id).deletion_state = "DELETED"
    remote.delete(key)
    assert migrate(database, local, remote, journal) == 0
    assert not remote.exists(key)


def test_s3_generation_evaluation_report_download_and_deletion(s3_platform):
    from backend.app.services.lifecycle import purge_once

    settings, store, database = s3_platform
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        data, generation, _ = generate(client, settings)
        evaluation = submit(client, generation)
        assert Worker(settings, database, store).run_once()
        response = client.post(f"/api/v1/evaluations/{evaluation['id']}/governance-report")
        assert response.status_code == 201, response.text
        report = response.json()
        downloaded = client.get(f"/api/v1/artifacts/{report['id']}/download")
        assert downloaded.status_code == 200
        assert len(downloaded.content) == report["size_bytes"]
        assert hashlib.sha256(downloaded.content).hexdigest() == report["sha256"]
        pid = generation["project_id"]
        name = client.get(f"/api/v1/projects/{pid}").json()["name"]
        assert (
            client.post(f"/api/v1/projects/{pid}/deletion", json={"confirmation": name}).status_code
            == 202
        )
        assert purge_once(database, store)
        assert not store.client.list_objects_v2(Bucket=settings.s3_bucket).get("Contents")
        assert client.get(f"/api/v1/artifacts/{report['id']}/download").status_code == 404
