"""Environment configuration; relative paths resolve against the repository."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import quote, urlsplit

from .version import APPLICATION_VERSION

ROOT = Path(__file__).resolve().parents[2]


def positive_int(value: str, name: str, maximum: int) -> int:
    try:
        number = int(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not 1 <= number <= maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return number


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 5000
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    max_upload_mb: int = 10
    generated_dir: Path = ROOT / "backend/generated_data"
    upload_dir: Path = ROOT / "backend/uploads"
    model_dir: Path = ROOT / "backend"
    log_level: str = "INFO"
    max_samples: int = 1000
    max_images: int = 64
    max_source_rows: int = 1000
    max_ecg_segments: int = 5000
    ecg_epochs: int = 10
    ecg_sampling_rate: int = 125
    enable_imaging_lab: bool = False
    database_url: str = "postgresql+psycopg://medsynth@127.0.0.1:55432/medsynth"
    artifact_storage_backend: str = "local"
    artifact_storage_path: Path = ROOT / "data/artifacts"
    job_poll_interval: int = 2
    job_max_attempts: int = 3
    job_lease_seconds: int = 60
    job_heartbeat_seconds: int = 10
    tabular_max_source_rows: int = 10000
    tabular_max_columns: int = 100
    tabular_max_generated_rows: int = 10000
    tabular_max_transformed_cells: int = 2000000
    ctgan_max_epochs: int = 50
    tvae_max_epochs: int = 50
    ctgan_warning_min_rows: int = 500
    tvae_warning_min_rows: int = 500
    tabular_job_timeout_seconds: int = 300
    evaluation_timeout_seconds: int = 300
    dcr_max_rows: int = 2000
    disclosure_max_rows: int = 2000
    disclosure_estimate_rows: int = 500
    disclosure_estimate_iterations: int = 3
    quality_subsample_rows: int = 2000
    utility_max_rows: int = 10000
    utility_max_encoded_cells: int = 2000000
    app_version: str = APPLICATION_VERSION
    app_commit: str | None = None
    app_build_timestamp: str | None = None
    auth_mode: str = "development"
    debug_enabled: bool = False
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_internal_origin: str | None = None
    oidc_client_secret: str = field(default="", repr=False)
    oidc_redirect_uri: str = "http://127.0.0.1:5000/api/v1/auth/callback"
    frontend_url: str = "http://127.0.0.1:5173"
    session_secret: str = field(default="", repr=False)
    session_hours: int = 8
    s3_endpoint: str | None = None
    s3_region: str = "us-east-1"
    s3_bucket: str = ""
    s3_access_key: str | None = field(default=None, repr=False)
    s3_secret_key: str | None = field(default=None, repr=False)
    s3_server_side_encryption: str | None = None
    metrics_token: str = field(default="", repr=False)
    worker_metrics_port: int = 0

    def validate_security(self):
        if self.app_env not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test, or production")
        if not 1 <= self.session_hours <= 24:
            raise ValueError("SESSION_HOURS must be between 1 and 24")
        if self.auth_mode not in {"development", "oidc"}:
            raise ValueError("AUTH_MODE must be development or oidc")
        if self.artifact_storage_backend not in {"local", "s3"}:
            raise ValueError("ARTIFACT_STORAGE_BACKEND must be local or s3")
        for origin in (
            *self.cors_origins,
            self.frontend_url,
            *([self.oidc_internal_origin] if self.oidc_internal_origin else []),
        ):
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or parsed.username
                or "*" in origin
            ):
                raise ValueError("Browser origins must be explicit HTTP(S) origins")
        if self.auth_mode == "oidc" and (
            not self.oidc_issuer or not self.oidc_client_id or len(self.session_secret) < 32
        ):
            raise ValueError(
                "OIDC requires issuer, client ID and a session secret of at least 32 characters"
            )
        for endpoint in (
            [self.oidc_issuer, self.oidc_redirect_uri] if self.auth_mode == "oidc" else []
        ) + ([self.s3_endpoint] if self.s3_endpoint else []):
            parsed = urlsplit(endpoint)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "Identity/storage endpoints must be explicit HTTP(S) URLs without embedded credentials or query strings"
                )
        if self.artifact_storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("S3_BUCKET is required")
        if bool(self.s3_access_key) != bool(self.s3_secret_key):
            raise ValueError("Supply both S3 credentials or use the standard credential provider")
        if self.s3_server_side_encryption not in {None, "AES256", "aws:kms"}:
            raise ValueError("Unsupported S3 server-side encryption setting")
        if self.app_env == "production":
            if (
                self.auth_mode != "oidc"
                or self.debug_enabled
                or self.log_level == "DEBUG"
                or self.artifact_storage_backend != "s3"
                or not self.cors_origins
            ):
                raise ValueError(
                    "Production requires OIDC, S3, explicit CORS and non-debug logging"
                )
            if len(set(self.session_secret)) < 12:
                raise ValueError("SESSION_SECRET must be a generated secret")
            if not self.metrics_token or len(self.metrics_token) < 32:
                raise ValueError("Production requires a generated internal METRICS_TOKEN")
            for url in (
                *self.cors_origins,
                self.frontend_url,
                self.oidc_issuer,
                self.oidc_redirect_uri,
                *([self.s3_endpoint] if self.s3_endpoint else []),
                *([self.oidc_internal_origin] if self.oidc_internal_origin else []),
            ):
                if not url.startswith("https://"):
                    raise ValueError(
                        "Production browser, identity and storage endpoints require HTTPS"
                    )
            from sqlalchemy.engine import make_url

            password = make_url(self.database_url).password
            if not password or password.lower() in {
                "password",
                "postgres",
                "medsynth",
                "changeme",
                "admin",
            }:
                raise ValueError("Production database credentials must be configured")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env

        def path(name: str, default: str) -> Path:
            supplied = Path(env.get(name, default)).expanduser()
            return (ROOT / supplied).resolve() if not supplied.is_absolute() else supplied.resolve()

        origins = tuple(
            x.strip()
            for x in env.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(
                ","
            )
            if x.strip()
        )
        if any(not x.startswith(("http://", "https://")) or "*" in x for x in origins):
            raise ValueError("CORS_ORIGINS must contain explicit HTTP(S) origins")
        app_env = env.get("APP_ENV", "development")
        if app_env not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test, or production")
        level = env.get("LOG_LEVEL", "INFO").upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("Invalid LOG_LEVEL")
        lab = env.get("ENABLE_IMAGING_LAB", "false").lower()
        if lab not in {"true", "false"}:
            raise ValueError("ENABLE_IMAGING_LAB must be true or false")
        database_url = env.get("DATABASE_URL") or (
            "postgresql+psycopg://"
            + quote(env.get("POSTGRES_USER", "medsynth"), safe="")
            + (
                ":" + quote(env["POSTGRES_PASSWORD"], safe="")
                if env.get("POSTGRES_PASSWORD")
                else ""
            )
            + "@127.0.0.1:"
            + str(positive_int(env.get("POSTGRES_PORT", "55432"), "POSTGRES_PORT", 65535))
            + "/"
            + quote(env.get("POSTGRES_DB", "medsynth"), safe="")
        )
        if not database_url.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use PostgreSQL with the psycopg driver")
        lease = positive_int(env.get("JOB_LEASE_SECONDS", "60"), "JOB_LEASE_SECONDS", 3600)
        heartbeat = positive_int(
            env.get("JOB_HEARTBEAT_SECONDS", "10"), "JOB_HEARTBEAT_SECONDS", 300
        )
        if lease < heartbeat * 3:
            raise ValueError("JOB_LEASE_SECONDS must be at least three heartbeat intervals")
        settings = cls(
            app_env=app_env,
            host=env.get("APP_HOST", "127.0.0.1"),
            port=positive_int(env.get("APP_PORT", "5000"), "APP_PORT", 65535),
            cors_origins=origins,
            max_upload_mb=positive_int(env.get("MAX_UPLOAD_MB", "10"), "MAX_UPLOAD_MB", 100),
            generated_dir=path("GENERATED_DATA_DIR", "backend/generated_data"),
            upload_dir=path("UPLOAD_DIR", "backend/uploads"),
            model_dir=path("MODEL_DIR", "backend"),
            log_level=level,
            max_samples=positive_int(
                env.get("MAX_GENERATION_SAMPLES", "1000"), "MAX_GENERATION_SAMPLES", 10000
            ),
            max_images=positive_int(
                env.get("MAX_GENERATION_IMAGES", "64"), "MAX_GENERATION_IMAGES", 256
            ),
            max_source_rows=positive_int(
                env.get("MAX_SOURCE_ROWS", "1000"), "MAX_SOURCE_ROWS", 10000
            ),
            max_ecg_segments=positive_int(
                env.get("MAX_ECG_SEGMENTS", "5000"), "MAX_ECG_SEGMENTS", 20000
            ),
            ecg_epochs=positive_int(env.get("ECG_EPOCHS", "10"), "ECG_EPOCHS", 50),
            ecg_sampling_rate=positive_int(
                env.get("ECG_SAMPLING_RATE", "125"), "ECG_SAMPLING_RATE", 1000
            ),
            enable_imaging_lab=lab == "true" and app_env != "production",
            database_url=database_url,
            artifact_storage_path=path("ARTIFACT_STORAGE_PATH", "data/artifacts"),
            job_poll_interval=positive_int(
                env.get("JOB_POLL_INTERVAL", "2"), "JOB_POLL_INTERVAL", 60
            ),
            job_max_attempts=positive_int(env.get("JOB_MAX_ATTEMPTS", "3"), "JOB_MAX_ATTEMPTS", 5),
            job_lease_seconds=lease,
            job_heartbeat_seconds=heartbeat,
            **{
                key: positive_int(env.get(key.upper(), str(default)), key.upper(), maximum)
                for key, default, maximum in (
                    ("tabular_max_source_rows", 10000, 100000),
                    ("tabular_max_columns", 100, 500),
                    ("tabular_max_generated_rows", 10000, 10000),
                    ("tabular_max_transformed_cells", 2000000, 10000000),
                    ("ctgan_max_epochs", 50, 100),
                    ("tvae_max_epochs", 50, 100),
                    ("ctgan_warning_min_rows", 500, 100000),
                    ("tvae_warning_min_rows", 500, 100000),
                    ("tabular_job_timeout_seconds", 300, 3600),
                    ("evaluation_timeout_seconds", 300, 3600),
                    ("dcr_max_rows", 2000, 5000),
                    ("disclosure_max_rows", 2000, 5000),
                    ("disclosure_estimate_rows", 500, 2000),
                    ("disclosure_estimate_iterations", 3, 10),
                    ("quality_subsample_rows", 2000, 10000),
                    ("utility_max_rows", 10000, 100000),
                    ("utility_max_encoded_cells", 2000000, 10000000),
                )
            },
            app_version=env.get("APP_VERSION", APPLICATION_VERSION),
            app_commit=env.get("APP_COMMIT") or None,
            app_build_timestamp=env.get("APP_BUILD_TIMESTAMP") or None,
            auth_mode=env.get("AUTH_MODE", "development"),
            debug_enabled=env.get("APP_DEBUG", "false").lower() == "true",
            oidc_issuer=env.get("OIDC_ISSUER", "").rstrip("/"),
            oidc_client_id=env.get("OIDC_CLIENT_ID", ""),
            oidc_internal_origin=env.get("OIDC_INTERNAL_ORIGIN") or None,
            oidc_client_secret=env.get("OIDC_CLIENT_SECRET", ""),
            oidc_redirect_uri=env.get(
                "OIDC_REDIRECT_URI", "http://127.0.0.1:5000/api/v1/auth/callback"
            ),
            frontend_url=env.get("FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/"),
            session_secret=env.get("SESSION_SECRET", ""),
            session_hours=positive_int(env.get("SESSION_HOURS", "8"), "SESSION_HOURS", 24),
            artifact_storage_backend=env.get("ARTIFACT_STORAGE_BACKEND", "local"),
            s3_endpoint=env.get("S3_ENDPOINT") or None,
            s3_bucket=env.get("S3_BUCKET", ""),
            s3_region=env.get("S3_REGION", "us-east-1"),
            s3_access_key=env.get("S3_ACCESS_KEY") or None,
            s3_secret_key=env.get("S3_SECRET_KEY") or None,
            s3_server_side_encryption=env.get("S3_SERVER_SIDE_ENCRYPTION") or None,
            metrics_token=env.get("METRICS_TOKEN", ""),
            worker_metrics_port=positive_int(
                env["WORKER_METRICS_PORT"], "WORKER_METRICS_PORT", 65535
            )
            if env.get("WORKER_METRICS_PORT")
            else 0,
        )
        settings.validate_security()
        return settings
