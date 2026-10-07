from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .api.errors import install_handlers
from .api.middleware import RequestMiddleware
from .api.router import router
from .config import Settings
from .core.logging import configure_logging, log_event
from .core.runtime import Runtime
from .db.session import Database
from .security.oidc import OIDCClient
from .storage.factory import artifact_store


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.validate_security()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database = Database(settings)
        app.state.runtime = Runtime(settings, database, artifact_store(settings))
        log_event("api_started")
        try:
            yield
        finally:
            database.dispose()
            log_event("api_stopped")

    app = FastAPI(
        title="MedSynth Guard",
        version=settings.app_version,
        description="Persistent synthetic health data workflows. ECG is Beta; imaging is Experimental. No privacy or clinical release certification.",
        debug=False,
        docs_url=None if settings.app_env == "production" else "/docs",
        redoc_url=None if settings.app_env == "production" else "/redoc",
        openapi_url=None if settings.app_env == "production" else "/openapi.json",
        lifespan=lifespan,
    )
    install_handlers(app)
    if settings.auth_mode == "oidc":
        oauth = OAuth()
        oauth.register(
            "identity",
            client_cls=OIDCClient,
            public_issuer=settings.oidc_issuer,
            internal_origin=settings.oidc_internal_origin,
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret or None,
            server_metadata_url=(
                settings.oidc_internal_origin + urlsplit(settings.oidc_issuer).path
                if settings.oidc_internal_origin
                else settings.oidc_issuer
            )
            + "/.well-known/openid-configuration",
            client_kwargs={"scope": "openid profile email", "code_challenge_method": "S256"},
        )
        app.state.oauth = oauth
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret or "explicit-local-development-state-only",
        session_cookie="medsynth_oidc_state",
        max_age=600,
        same_site="lax",
        https_only=settings.app_env == "production",
    )
    app.include_router(router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=[
            "Content-Type",
            "Idempotency-Key",
            "X-Request-ID",
            "X-CSRF-Token",
            "X-Organization-ID",
        ],
        expose_headers=["X-Request-ID"],
        allow_credentials=True,
    )
    app.add_middleware(
        RequestMiddleware,
        max_bytes=settings.max_upload_mb * 1024**2,
        production=settings.app_env == "production",
    )
    return app
