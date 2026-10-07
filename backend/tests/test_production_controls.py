import asyncio
import json
import logging
import secrets
from dataclasses import replace

import pytest
from authlib.integrations.starlette_client import StarletteOAuth2App
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.app.config import Settings
from backend.app.core.logging import JsonFormatter, job_context, request_id_context
from backend.app.core.metrics import STORAGE_FAILURES, STORAGE_LATENCY
from backend.app.security.oidc import OIDCClient
from backend.app.storage.instrumented import ObservedArtifactStore


def test_private_oidc_backchannel_preserves_browser_issuer_and_authorization(monkeypatch):
    async def discovery(self):
        return {
            "issuer": "https://identity.example/realm",
            "authorization_endpoint": "https://identity.example/authorize",
            "token_endpoint": "https://identity.example/token",
            "jwks_uri": "https://identity.example/keys",
        }

    monkeypatch.setattr(StarletteOAuth2App, "load_server_metadata", discovery)
    client = OIDCClient(
        framework=None,
        name="identity",
        public_issuer="https://identity.example/realm",
        internal_origin="https://identity.internal",
    )
    metadata = asyncio.run(client.load_server_metadata())
    assert metadata["issuer"] == "https://identity.example/realm"
    assert metadata["authorization_endpoint"] == "https://identity.example/authorize"
    assert metadata["token_endpoint"] == "https://identity.internal/token"
    assert metadata["jwks_uri"] == "https://identity.internal/keys"
    client.public_issuer = "https://another.example/realm"
    with pytest.raises(ValueError, match="issuer"):
        asyncio.run(client.load_server_metadata())


def test_production_rejects_insecure_configuration():
    valid = Settings(
        app_env="production",
        auth_mode="oidc",
        oidc_issuer="https://identity.example/realm",
        oidc_client_id="app",
        session_secret=secrets.token_urlsafe(32),
        metrics_token=secrets.token_urlsafe(32),
        artifact_storage_backend="s3",
        s3_bucket="private",
        database_url="postgresql+psycopg://app:long-random-secret@db/app",
        frontend_url="https://app.example",
        cors_origins=("https://app.example",),
        oidc_redirect_uri="https://app.example/api/v1/auth/callback",
    )
    valid.validate_security()
    for change in (
        {"auth_mode": "development"},
        {"debug_enabled": True},
        {"cors_origins": ("*",)},
        {"artifact_storage_backend": "local"},
        {"session_secret": "short"},
        {"oidc_issuer": ""},
        {"oidc_internal_origin": "https://id.internal/path"},
        {"frontend_url": "http://app.example"},
        {"metrics_token": ""},
    ):
        with pytest.raises(ValueError):
            replace(valid, **change).validate_security()


def test_storage_metrics_count_operations_and_failures_without_keys():
    class Broken:
        def ready(self):
            raise OSError("unavailable")

    store = ObservedArtifactStore(Broken(), "local")
    failures = STORAGE_FAILURES.labels("ready", "local")._value.get()
    observations = STORAGE_LATENCY.labels("ready", "local")._sum.get()
    with pytest.raises(OSError):
        store.ready()
    assert STORAGE_FAILURES.labels("ready", "local")._value.get() == failures + 1
    assert STORAGE_LATENCY.labels("ready", "local")._sum.get() >= observations


def test_production_http_headers_cors_and_internal_boundaries():
    settings = Settings(
        app_env="production",
        auth_mode="oidc",
        oidc_issuer="https://identity.example/realm",
        oidc_client_id="app",
        session_secret=secrets.token_urlsafe(32),
        metrics_token=secrets.token_urlsafe(32),
        artifact_storage_backend="s3",
        s3_endpoint="https://storage.example",
        s3_bucket="private",
        s3_access_key=secrets.token_urlsafe(32),
        s3_secret_key=secrets.token_urlsafe(32),
        database_url="postgresql+psycopg://app:long-random-secret@127.0.0.1:1/missing",
        frontend_url="https://app.example",
        cors_origins=("https://app.example",),
        oidc_redirect_uri="https://app.example/api/v1/auth/callback",
    )
    with TestClient(create_app(settings), base_url="https://app.example") as client:
        response = client.get("/health", headers={"Origin": "https://app.example"})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://app.example"
        assert response.headers["access-control-allow-credentials"] == "true"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert "max-age=" in response.headers["strict-transport-security"]
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert "camera=()" in response.headers["permissions-policy"]
        assert (
            "access-control-allow-origin"
            not in client.get("/health", headers={"Origin": "https://untrusted.example"}).headers
        )
        assert client.get("/docs").status_code == 404
        assert client.get("/internal/metrics").status_code == 404
        assert client.get("/api/v1/projects").status_code == 401


def test_structured_logs_retain_context_and_drop_fake_secrets_and_patient_values():
    secret = "fixture-secret-DO-NOT-LOG"
    patient = "fixture-patient-DO-NOT-LOG"
    record = logging.LogRecord("httpx", logging.INFO, "", 0, secret + patient, (), None)
    request = request_id_context.set("request-fixture")
    job = job_context.set({"job_id": "job-fixture"})
    try:
        output = JsonFormatter().format(record)
        assert secret not in output and patient not in output
        record.event = "http_request"
        record.user_id = "user-fixture"
        record.organization_id = "organization-fixture"
        record.token = secret
        record.patient = patient
        output = JsonFormatter().format(record)
        parsed = json.loads(output)
        assert parsed["request_id"] == "request-fixture"
        assert parsed["job_id"] == "job-fixture"
        assert parsed["user_id"] == "user-fixture"
        assert parsed["organization_id"] == "organization-fixture"
        assert secret not in output and patient not in output
    finally:
        request_id_context.reset(request)
        job_context.reset(job)
