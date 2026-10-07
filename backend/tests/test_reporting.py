"""Persisted report rendering and product API security checks on real PostgreSQL."""

import hashlib
from uuid import UUID

import pytest
from sqlalchemy import event

from backend.app.db.session import Database
from backend.app.storage.local import LocalArtifactStore
from backend.app.workers.runner import Worker
from backend.tests.test_evaluation_integration import generate, submit

pytestmark = pytest.mark.integration


def test_report_registered_escaped_idempotent_and_integrity(pg_client, pg_settings, monkeypatch):
    dataset, generation, raw = generate(pg_client, pg_settings)
    pid = generation["project_id"]
    pg_client.patch(f"/api/v1/projects/{pid}", json={"name": "Research <script>alert(1)</script>"})
    evaluation = submit(pg_client, generation)
    database = Database(pg_settings)
    try:
        assert Worker(
            pg_settings, database, LocalArtifactStore(pg_settings.artifact_storage_path)
        ).run_once()
    finally:
        database.dispose()
    # Report creation must not execute evaluation again.
    monkeypatch.setattr(
        "backend.app.services.evaluation.execution.execute",
        lambda *a, **k: pytest.fail("Report recomputed metrics"),
    )
    path = f"/api/v1/evaluations/{evaluation['id']}/governance-report"
    response = pg_client.post(path)
    assert response.status_code == 201, response.text
    report = response.json()
    assert report["artifact_type"] == "GOVERNANCE_REPORT"
    assert report["metadata_json"]["evaluation_run_id"] == evaluation["id"]
    assert report["created_at"] and report["downloadable"]
    assert pg_client.post(path).json()["id"] == report["id"]
    download = pg_client.get(f"/api/v1/artifacts/{report['id']}/download")
    assert download.status_code == 200
    assert len(download.content) == report["size_bytes"]
    assert hashlib.sha256(download.content).hexdigest() == report["sha256"]
    for section in (
        "Executive summary",
        "Generation configuration",
        "Schema governance",
        "Statistical fidelity",
        "Privacy diagnostics",
        "ML utility",
        "Release policy",
        "Decision rationale",
        "Provenance",
        "application_build_timestamp",
        "Warnings and limitations",
    ):
        assert section in download.text
    assert "<script>" not in download.text
    assert "&lt;script&gt;" in download.text
    assert raw.decode().splitlines()[1] not in download.text
    assert str(pg_settings.artifact_storage_path) not in download.text
    assert "&gt;= None" not in download.text and "&lt;= None" not in download.text
    for forbidden in (
        "storage_key",
        "source_path",
        "HIPAA compliant",
        "GDPR compliant",
        "100% anonymous",
        "zero privacy risk",
        "safe to share",
        "re-identification impossible",
    ):
        assert forbidden.lower() not in download.text.lower()
    # Registered integrity metadata is still enforced.
    from backend.app.db.models import Artifact

    database = Database(pg_settings)
    try:
        with database.sessions() as session:
            record = session.get(Artifact, UUID(report["id"]))
            store = LocalArtifactStore(pg_settings.artifact_storage_path)
            (store.root / record.storage_key).write_bytes(b"changed")
        assert pg_client.get(f"/api/v1/artifacts/{report['id']}/download").status_code == 503
    finally:
        database.dispose()


def test_workspace_summaries_governance_filters_and_incomplete_report(pg_client, pg_settings):
    dataset, generation, _ = generate(pg_client, pg_settings)
    pid = generation["project_id"]
    r = pg_client.put(
        f"/api/v1/datasets/{dataset['id']}/tabular/governance",
        json={"overrides": {"age": {"annotations": ["QUASI_IDENTIFIER"]}}},
    )
    assert r.status_code == 200 and r.json()["metadata_json"]["governance_overrides"]["age"][
        "annotations"
    ] == ["QUASI_IDENTIFIER"]
    assert (
        pg_client.put(
            f"/api/v1/datasets/{dataset['id']}/tabular/governance",
            json={"overrides": {"clinical_notes": {"role": "MODELLED"}}},
        ).status_code
        == 400
    )
    response = pg_client.get(f"/api/v1/workspace/projects/{pid}/summary")
    assert response.status_code == 200, response.text
    assert response.json()["datasets"] == response.json()["runs"] == 1
    assert response.json()["evaluations"] == 0
    assert (
        pg_client.get(f"/api/v1/workspace/runs?project_id={pid}&status=FAILED").json()["total"] == 0
    )
    assert (
        pg_client.get(
            f"/api/v1/workspace/runs?project_id={pid}&engine=gaussian_copula&limit=1"
        ).json()["total"]
        == 1
    )
    assert pg_client.get("/api/v1/workspace/runs?limit=101").status_code == 422
    activity = pg_client.get(f"/api/v1/workspace/activity?project_id={pid}").json()
    assert any(a["event_type"] == "SCHEMA_GOVERNANCE_SAVED" for a in activity["items"])
    assert all("metadata_json" not in a for a in activity["items"])
    evaluation = submit(pg_client, generation)
    assert (
        pg_client.post(f"/api/v1/evaluations/{evaluation['id']}/governance-report").status_code
        == 409
    )
    # Lists batch lifecycle reads rather than one execution query per evaluation.
    database = pg_client.app.state.runtime.database
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(database.engine, "before_cursor_execute", record)
    try:
        response = pg_client.get(f"/api/v1/workspace/evaluations?project_id={pid}")
        assert response.status_code == 200 and response.json()["total"] == 1
        assert len(statements) <= 4
    finally:
        event.remove(database.engine, "before_cursor_execute", record)
