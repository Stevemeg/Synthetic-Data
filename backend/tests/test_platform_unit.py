import hashlib
import io
from datetime import datetime, timezone
from itertools import product
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.app.config import Settings
from backend.app.core.errors import AppError
from backend.app.schemas.platform import JobCreate
from backend.app.services.jobs.failures import classify_failure
from backend.app.services.jobs.provenance import build_manifest
from backend.app.services.jobs.service import fingerprint
from backend.app.services.jobs.state import TRANSITIONS, JobStatus, validate_transition
from backend.app.storage.local import LocalArtifactStore


@pytest.mark.parametrize("source,target", list(product(JobStatus, repeat=2)))
def test_all_state_transitions(source, target):
    if target in TRANSITIONS[source]:
        validate_transition(source, target)
    else:
        with pytest.raises(AppError):
            validate_transition(source, target)


@pytest.mark.parametrize(
    "key", ["../outside", "/absolute", "a/../b", "a//b", "a/./b", "a\\b", "", "a:b", "a/%2e%2e"]
)
def test_storage_rejects_unsafe_keys(tmp_path, key):
    store = LocalArtifactStore(tmp_path / "store")
    with pytest.raises((AppError, ValueError)):
        store.put(key, io.BytesIO(b"test"))


def test_storage_integrity_and_immutability(tmp_path):
    store = LocalArtifactStore(tmp_path / "store")
    content = b"synthetic fixture"
    info = store.put("project/run/output.csv", io.BytesIO(content))
    assert info.sha256 == hashlib.sha256(content).hexdigest()
    assert info.size_bytes == len(content)
    assert store.exists("project/run/output.csv")
    with store.get("project/run/output.csv") as stream:
        assert stream.read() == content
    assert store.metadata("project/run/output.csv") == info
    with pytest.raises(FileExistsError):
        store.put("project/run/output.csv", io.BytesIO(b"overwrite"))
    store.delete("project/run/output.csv")
    assert not store.exists("project/run/output.csv")


def test_storage_symlink_rejected(tmp_path):
    store = LocalArtifactStore(tmp_path / "store")
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (store.root / "link").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not grant symbolic link creation")
    with pytest.raises(AppError):
        store.put("link/leak", io.BytesIO(b"x"))


def test_fingerprint_equivalence():
    dataset = uuid4()
    first = JobCreate(modality="timeseries", dataset_id=dataset, requested_samples=2)
    assert fingerprint(first) == fingerprint(JobCreate.model_validate(first.model_dump()))
    assert fingerprint(first) != fingerprint(first.model_copy(update={"requested_samples": 3}))


def test_retry_classification():
    assert classify_failure(OSError("private")).retryable
    assert not classify_failure(AppError("Bad input", "INVALID_ECG")).retryable
    failure = classify_failure(RuntimeError("patient=secret"))
    assert not failure.retryable and "secret" not in failure.message
    assert not classify_failure(FileNotFoundError("private")).retryable


@pytest.mark.parametrize(
    "env",
    [
        {"DATABASE_URL": "sqlite:///test"},
        {"ARTIFACT_STORAGE_BACKEND": "s3"},
        {"JOB_LEASE_SECONDS": "10", "JOB_HEARTBEAT_SECONDS": "10"},
        {"JOB_MAX_ATTEMPTS": "6"},
    ],
)
def test_platform_configuration_rejected(env):
    with pytest.raises(ValueError):
        Settings.from_env(env)


def test_platform_configuration_paths_and_password():
    settings = Settings.from_env(
        {
            "POSTGRES_PASSWORD": "a@:/b",
            "ARTIFACT_STORAGE_PATH": "data/test",
            "JOB_MAX_ATTEMPTS": "2",
        }
    )
    assert "a%40%3A%2Fb" in settings.database_url
    assert settings.artifact_storage_path.is_absolute()
    assert settings.job_max_attempts == 2


def test_provenance_contract(settings):
    now = datetime.now(timezone.utc)
    job = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        modality="timeseries",
        engine="pytorch-ecg-vae",
        configuration_json={"ecg_epochs": 1},
        random_seed=42,
        requested_samples=2,
        started_at=now,
        attempt_count=1,
    )
    dataset = SimpleNamespace(id=uuid4(), sha256="a" * 64)
    result = {
        "metadata": {
            "produced_sample_count": 2,
            "maturity": "Beta",
            "warnings": [],
            "source_schema_summary": {"sequence_length": 96},
        }
    }
    manifest = build_manifest(
        job, dataset, result, [], {"identifier": "vae", "sha256": "b" * 64}, now, settings
    )
    assert manifest["source_dataset_sha256"] == "a" * 64
    assert manifest["produced_count"] == manifest["requested_count"] == 2
    assert manifest["model"]["sha256"] == "b" * 64
    result["metadata"]["produced_sample_count"] = 1
    with pytest.raises(ValueError):
        build_manifest(job, dataset, result, [], {}, now, settings)
