"""Phase 1 HTTP checks migrated to the official FastAPI contract."""

from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app


def test_health_readiness_openapi(client, app):
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503
    assert "/api/v1/projects/{project_id}/jobs" in client.get("/openapi.json").json()["paths"]
    assert client.get("/docs").status_code == 200
    assert not app.debug


def test_capabilities(client):
    caps = client.get("/api/v1/capabilities").json()["capabilities"]
    assert all(not caps[m]["available"] for m in ("genomic", "imaging"))
    if caps["tabular"]["available"]:
        assert {e["name"] for e in caps["tabular"]["engines"]} == {
            "gaussian_copula",
            "ctgan",
            "tvae",
        }


def test_cors_and_correlation(client):
    response = client.get(
        "/health", headers={"Origin": "http://localhost:5173", "X-Request-ID": "test-123"}
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["x-request-id"] == "test-123"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert (
        "access-control-allow-origin"
        not in client.get("/health", headers={"Origin": "https://untrusted.example"}).headers
    )


@pytest.mark.parametrize("count", [0, -1, 10001, True, 1.5, "10"])
def test_invalid_count(client, count):
    response = client.post(
        f"/api/v1/projects/{uuid4()}/jobs",
        json={"modality": "timeseries", "requested_samples": count},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/projects/bad",
        "/api/v1/jobs/bad",
        "/api/v1/artifacts/bad/download",
        "/api/v1/datasets/bad",
    ],
)
def test_invalid_ids(client, path):
    assert client.get(path).status_code == 422


@pytest.mark.parametrize("raw", ["{", "[]", "null", '"text"'])
def test_malformed_json(client, raw):
    response = client.post(
        "/api/v1/projects", content=raw, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_size_bound(settings):
    with TestClient(create_app(replace(settings, max_upload_mb=1))) as client:
        assert client.post("/api/v1/projects", content=b"x" * (1024**2 + 1)).status_code == 413


def test_database_errors_sanitized(client):
    response = client.get("/api/v1/projects")
    assert response.status_code == 503
    assert "nobody" not in response.text and "Traceback" not in response.text


def test_no_legacy_or_filesystem_endpoint(client):
    assert client.post("/api/generate/timeseries").status_code == 404
    assert client.get("/generated/secret/dataset.npz").status_code == 404


def test_error_contract_unknown_exception(client, monkeypatch):
    def fail(*args):
        raise RuntimeError("patient=secret; C:/private/file")

    monkeypatch.setattr("backend.app.services.projects.service.ProjectService.list", fail)
    response = client.get("/api/v1/projects", headers={"X-Request-ID": "exception-test"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert response.headers["x-request-id"] == "exception-test"
    assert "secret" not in response.text and "private" not in response.text
