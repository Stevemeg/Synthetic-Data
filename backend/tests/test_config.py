from pathlib import Path

import pytest

from backend.app.config import ROOT, Settings


def test_safe_defaults_and_cwd_independence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = Settings.from_env({})
    assert settings.host == "127.0.0.1"
    assert settings.model_dir == ROOT / "backend"
    assert not settings.enable_imaging_lab
    assert "*" not in settings.cors_origins


def test_environment_configuration(tmp_path):
    settings = Settings.from_env(
        {
            "APP_PORT": "5100",
            "UPLOAD_DIR": str(tmp_path),
            "GENERATED_DATA_DIR": "custom_data",
            "MAX_UPLOAD_MB": "2",
            "CORS_ORIGINS": "https://example.test",
            "LOG_LEVEL": "warning",
        }
    )
    assert settings.port == 5100 and settings.max_upload_mb == 2
    assert settings.upload_dir == tmp_path
    assert settings.generated_dir == ROOT / "custom_data"
    assert settings.log_level == "WARNING"
    assert settings.cors_origins == ("https://example.test",)
    assert isinstance(settings.model_dir, Path)


@pytest.mark.parametrize(
    "env",
    [
        {"APP_PORT": "abc"},
        {"APP_PORT": "0"},
        {"MAX_UPLOAD_MB": "101"},
        {"MAX_GENERATION_SAMPLES": "-1"},
        {"ECG_EPOCHS": "51"},
        {"ECG_SAMPLING_RATE": "0"},
        {"CORS_ORIGINS": "*"},
        {"APP_ENV": "unknown"},
        {"LOG_LEVEL": "all"},
        {"ENABLE_IMAGING_LAB": "yes"},
    ],
)
def test_invalid_configuration(env):
    with pytest.raises(ValueError):
        Settings.from_env(env)


def test_imaging_production_gate():
    assert Settings.from_env({"ENABLE_IMAGING_LAB": "true"}).enable_imaging_lab
    with pytest.raises(ValueError, match="Production requires"):
        Settings.from_env({"ENABLE_IMAGING_LAB": "true", "APP_ENV": "production"})
    assert not Settings.from_env(production_environment()).enable_imaging_lab


def production_environment():
    return {
        "APP_ENV": "production",
        "AUTH_MODE": "oidc",
        "OIDC_ISSUER": "https://identity.example.test/realm",
        "OIDC_CLIENT_ID": "medsynth",
        "OIDC_REDIRECT_URI": "https://app.example.test/api/v1/auth/callback",
        "FRONTEND_URL": "https://app.example.test",
        "CORS_ORIGINS": "https://app.example.test",
        "SESSION_SECRET": "test-only-distinct-generated-placeholder-987654321",
        "METRICS_TOKEN": "test-only-internal-metrics-placeholder-987654321",
        "ARTIFACT_STORAGE_BACKEND": "s3",
        "S3_BUCKET": "private-test-artifacts",
        "ENABLE_IMAGING_LAB": "true",
        "DATABASE_URL": "postgresql+psycopg://test:test-only-placeholder@database/medsynth",
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"AUTH_MODE": "development"},
        {"LOG_LEVEL": "DEBUG"},
        {"CORS_ORIGINS": "*"},
        {"SESSION_SECRET": ""},
        {"ARTIFACT_STORAGE_BACKEND": "local"},
        {"OIDC_ISSUER": "http://identity.example.test"},
        {"METRICS_TOKEN": ""},
        {"DATABASE_URL": "postgresql+psycopg://postgres:postgres@db/app"},
    ],
)
def test_production_rejects_insecure_configuration(changes):
    with pytest.raises(ValueError):
        Settings.from_env({**production_environment(), **changes})
