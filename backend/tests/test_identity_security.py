"""Real PostgreSQL session, role and IDOR tests; OIDC browser verification is separate."""

import secrets
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from backend.app import create_app
from backend.app.db.models import (
    DEFAULT_ORGANIZATION_ID,
    AuditEvent,
    LoginSession,
    Organization,
    OrganizationMembership,
    Project,
    User,
)
from backend.app.db.session import Database
from backend.app.security.auth import COOKIE, digest_token
from backend.app.services.lifecycle import purge_once
from backend.app.storage.local import LocalArtifactStore
from backend.app.workers.runner import Worker
from backend.tests.test_evaluation_integration import generate, submit

pytestmark = pytest.mark.integration


@pytest.fixture
def identity_platform(pg_settings):
    settings = replace(
        pg_settings,
        auth_mode="oidc",
        oidc_issuer="https://identity.example.test/realms/test",
        oidc_client_id="test-client",
        session_secret=secrets.token_urlsafe(48),
    )
    database = Database(settings)
    credentials = {}
    with database.sessions.begin() as session:
        org_b = Organization(name="Second research organization", slug="second-research")
        session.add(org_b)
        session.flush()
        for name, org in (("a", DEFAULT_ORGANIZATION_ID), ("b", org_b.id)):
            user = User(
                issuer=settings.oidc_issuer,
                subject=f"external-subject-{name}",
                display_name=f"Test researcher {name}",
            )
            session.add(user)
            session.flush()
            session.add(OrganizationMembership(user_id=user.id, organization_id=org, role="OWNER"))
            token, csrf = secrets.token_urlsafe(32), secrets.token_hex(32)
            session.add(
                LoginSession(
                    token_hash=digest_token(token),
                    user_id=user.id,
                    csrf_token=csrf,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                )
            )
            credentials[name] = (token, csrf, org, user.id)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client, settings, database, credentials
    database.dispose()


def sign_in(client, credential):
    token, csrf, org, _ = credential
    client.cookies.set(COOKIE, token)
    client.headers.update(
        {"X-CSRF-Token": csrf, "Origin": "http://127.0.0.1:5173", "X-Organization-ID": str(org)}
    )


def test_unauthenticated_csrf_roles_logout(identity_platform):
    client, _, database, credentials = identity_platform
    assert client.get("/api/v1/projects").status_code == 401
    sign_in(client, credentials["a"])
    assert client.get("/api/v1/auth/me").json()["user"]["id"] == str(credentials["a"][3])
    own_members = client.get("/api/v1/organization/members").json()
    assert len(own_members) == 1
    assert (
        client.patch(
            f"/api/v1/organization/members/{own_members[0]['id']}", json={"role": "VIEWER"}
        ).status_code
        == 409
    )
    assert client.post("/api/v1/projects", json={"name": "Authorized research"}).status_code == 201
    client.headers["X-CSRF-Token"] = "forged"
    assert client.post("/api/v1/projects", json={"name": "Forbidden"}).status_code == 403
    sign_in(client, credentials["a"])
    with database.sessions.begin() as session:
        session.execute(
            update(OrganizationMembership)
            .where(OrganizationMembership.user_id == credentials["a"][3])
            .values(role="VIEWER")
        )
    assert client.get("/api/v1/projects").status_code == 200
    assert client.post("/api/v1/projects", json={"name": "Forbidden"}).status_code == 403
    assert client.get("/api/v1/organization/members").status_code == 403
    with database.sessions.begin() as session:
        session.execute(
            update(OrganizationMembership)
            .where(OrganizationMembership.user_id == credentials["a"][3])
            .values(role="EDITOR")
        )
    assert client.post("/api/v1/projects", json={"name": "Editor research"}).status_code == 201
    assert (
        client.patch(
            "/api/v1/organization/members/00000000-0000-4000-8000-000000000001",
            json={"role": "OWNER"},
        ).status_code
        == 403
    )
    old_cookie = credentials["a"][0]
    assert client.post("/api/v1/auth/logout").status_code == 200
    client.cookies.set(COOKIE, old_cookie)
    assert client.get("/api/v1/projects").status_code == 401


def test_full_cross_tenant_uuid_swapping_and_deletion(identity_platform, caplog):
    client, settings, database, credentials = identity_platform
    sign_in(client, credentials["b"])
    dataset, generation, _ = generate(client, settings)
    evaluation = submit(client, generation)
    assert Worker(settings, database, LocalArtifactStore(settings.artifact_storage_path)).run_once()
    report_response = client.post(f"/api/v1/evaluations/{evaluation['id']}/governance-report")
    assert report_response.status_code == 201, report_response.text
    report = report_response.json()
    artifacts = client.get(f"/api/v1/jobs/{generation['id']}/artifacts").json()["items"]
    pid, did, jid, eid = generation["project_id"], dataset["id"], generation["id"], evaluation["id"]
    policy = client.post(
        f"/api/v1/projects/{pid}/release-policies",
        json={
            "name": "Organization research policy",
            "version": 1,
            "rules": {"structural_validation": {"equals": True, "required": True}},
        },
    )
    assert policy.status_code == 201, policy.text
    # Backend capability matrix on actual resources (valid CSRF, no UI reliance).
    with database.sessions.begin() as session:
        session.execute(
            update(OrganizationMembership)
            .where(OrganizationMembership.user_id == credentials["b"][3])
            .values(role="VIEWER")
        )
    for method, path, body in (
        ("POST", f"/projects/{pid}/datasets", {}),
        ("POST", f"/datasets/{did}/tabular/preflight", {}),
        ("PUT", f"/datasets/{did}/tabular/governance", {"overrides": {}}),
        (
            "POST",
            f"/projects/{pid}/jobs",
            {
                "modality": "tabular",
                "dataset_id": did,
                "engine": "gaussian_copula",
                "requested_samples": 10,
            },
        ),
        ("POST", f"/generation-jobs/{jid}/evaluations", {"profile": "BASIC"}),
        ("POST", f"/evaluations/{eid}/governance-report", {}),
        ("POST", f"/projects/{pid}/release-policies", {}),
        ("POST", f"/projects/{pid}/deletion", {"confirmation": "Research"}),
    ):
        assert client.request(method, "/api/v1" + path, json=body).status_code == 403, path
    assert client.get(f"/api/v1/artifacts/{report['id']}/download").status_code == 200
    with database.sessions.begin() as session:
        session.execute(
            update(OrganizationMembership)
            .where(OrganizationMembership.user_id == credentials["b"][3])
            .values(role="EDITOR")
        )
    assert client.post(f"/api/v1/datasets/{did}/tabular/preflight").status_code == 200
    assert (
        client.put(f"/api/v1/datasets/{did}/tabular/governance", json={"overrides": {}}).status_code
        == 200
    )
    assert client.post(f"/api/v1/evaluations/{eid}/governance-report").status_code in {200, 201}
    assert client.post(f"/api/v1/projects/{pid}/release-policies", json={}).status_code == 403
    assert (
        client.post(
            f"/api/v1/projects/{pid}/deletion", json={"confirmation": "Research"}
        ).status_code
        == 403
    )
    with database.sessions.begin() as session:
        session.execute(
            update(OrganizationMembership)
            .where(OrganizationMembership.user_id == credentials["b"][3])
            .values(role="OWNER")
        )
    sign_in(client, credentials["a"])
    paths = [
        f"/projects/{pid}",
        f"/datasets/{did}",
        f"/jobs/{jid}",
        f"/evaluations/{eid}",
        f"/release-policies/{policy.json()['id']}",
        f"/artifacts/{report['id']}",
        f"/artifacts/{report['id']}/download",
        f"/evaluations/{eid}/reports",
        f"/jobs/{jid}/artifacts",
    ]
    paths += [f"/artifacts/{a['id']}/download" for a in artifacts]
    for path in paths:
        response = client.get("/api/v1" + path)
        assert response.status_code == 404, (path, response.status_code, response.text)
    for path, body in [
        (f"/datasets/{did}/tabular/preflight", {}),
        (f"/generation-jobs/{jid}/evaluations", {"profile": "BASIC"}),
        (f"/evaluations/{eid}/governance-report", {}),
        (f"/projects/{pid}/evaluations/compare", {"evaluation_ids": [eid, str(UUID(int=1))]}),
        (f"/projects/{pid}/deletion", {"confirmation": "Research"}),
        (
            f"/projects/{pid}/jobs",
            {"modality": "tabular", "dataset_id": did, "requested_samples": 10},
        ),
        (f"/jobs/{jid}/cancel", {}),
    ]:
        assert client.post("/api/v1" + path, json=body).status_code == 404, path
    for inventory in ("projects", "datasets", "runs", "evaluations", "reports", "activity"):
        response = client.get(f"/api/v1/workspace/{inventory}")
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 0, (inventory, response.text)
    assert (
        client.put(f"/api/v1/datasets/{did}/tabular/governance", json={"overrides": {}}).status_code
        == 404
    )
    own_project = client.post(
        "/api/v1/projects", json={"name": "First organization research"}
    ).json()
    assert (
        client.post(
            f"/api/v1/projects/{own_project['id']}/jobs",
            json={"modality": "tabular", "dataset_id": did, "requested_samples": 10},
        ).status_code
        == 404
    )
    # Explicitly selecting a foreign organization also fails before resource retrieval.
    client.headers["X-Organization-ID"] = str(credentials["b"][2])
    assert client.get(f"/api/v1/projects/{pid}").status_code == 403
    sign_in(client, credentials["b"])
    name = client.get(f"/api/v1/projects/{pid}").json()["name"]
    assert (
        client.post(
            f"/api/v1/projects/{pid}/deletion", json={"confirmation": "incorrect"}
        ).status_code
        == 422
    )
    assert (
        client.post(f"/api/v1/projects/{pid}/deletion", json={"confirmation": name}).status_code
        == 202
    )
    assert client.get(f"/api/v1/artifacts/{report['id']}/download").status_code == 404
    store = LocalArtifactStore(settings.artifact_storage_path)
    assert purge_once(database, store)
    with database.sessions() as session:
        assert session.get(Project, UUID(pid)).deletion_state == "DELETED"
        events = list(session.scalars(select(AuditEvent).where(AuditEvent.entity_id == UUID(pid))))
        assert any(e.actor == "user" and e.user_id == credentials["b"][3] for e in events)
        assert any(
            e.event_type == "PROJECT_PURGED" and e.organization_id == credentials["b"][2]
            for e in events
        )
    assert not list(store.root.rglob("source.csv"))
    assert "external-subject-" not in caplog.text
    assert credentials["b"][0] not in caplog.text


def test_worker_rejects_manipulated_cross_organization_source_reference(
    identity_platform, monkeypatch
):
    from sqlalchemy.exc import IntegrityError

    from backend.app.db.models import Artifact, GenerationJob
    from backend.tests.test_platform_integration import dataset, project

    client, settings, database, credentials = identity_platform
    sign_in(client, credentials["b"])
    foreign = dataset(client, project(client))
    sign_in(client, credentials["a"])
    pid = project(client)
    own = dataset(client, pid)
    response = client.post(
        f"/api/v1/projects/{pid}/jobs",
        json={"modality": "timeseries", "dataset_id": own["id"], "requested_samples": 2},
    )
    assert response.status_code == 202, response.text
    job_id = UUID(response.json()["id"])
    # Persisted references cannot be swapped by an unscoped ordinary SQL write.
    with pytest.raises(IntegrityError):
        with database.sessions.begin() as session:
            session.get(GenerationJob, job_id).dataset_id = UUID(foreign["id"])
    # Separately verify the worker against a corrupted detached claim snapshot.
    worker = Worker(settings, database, LocalArtifactStore(settings.artifact_storage_path))
    claim = worker.queue.claim(worker.worker_id)
    claim.job.dataset_id = UUID(foreign["id"])
    monkeypatch.setattr(worker.queue, "claim", lambda _: claim)
    assert worker.run_once()
    with database.sessions() as session:
        job = session.get(GenerationJob, job_id)
        assert job.status == "FAILED" and job.error_code == "TENANT_INVARIANT_FAILED"
        assert not list(session.scalars(select(Artifact).where(Artifact.job_id == job_id)))
