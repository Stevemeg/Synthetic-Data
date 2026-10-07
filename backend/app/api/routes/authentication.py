"""OIDC code + PKCE; short-lived signed state, revocable server-side login session."""

import secrets
from datetime import datetime, timedelta, timezone

from authlib.integrations.base_client.errors import OAuthError
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import delete, select

from ...core.errors import AppError
from ...db.models import AuditEvent, LoginSession, Organization, OrganizationMembership, User
from ...security.auth import COOKIE, digest_token

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.get("/login")
async def login(request: Request):
    settings = request.app.state.runtime.settings
    if settings.auth_mode != "oidc":
        raise AppError(
            "OIDC is not configured in this development workspace", "oidc_unavailable", 503
        )
    request.session.clear()
    return await request.app.state.oauth.identity.authorize_redirect(
        request, settings.oidc_redirect_uri, prompt="login"
    )


@router.get("/callback")
async def callback(request: Request):
    runtime = request.app.state.runtime
    if runtime.settings.auth_mode != "oidc":
        raise AppError("OIDC is unavailable", "oidc_unavailable", 503)
    try:
        token = await request.app.state.oauth.identity.authorize_access_token(
            request,
            claims_options={
                "iss": {"essential": True, "value": runtime.settings.oidc_issuer},
                "sub": {"essential": True},
            },
        )
        claims = token.get("userinfo")
        if not claims or claims.get("iss") != runtime.settings.oidc_issuer or not claims.get("sub"):
            raise AppError("Identity verification failed", "authentication_failed", 401)
    except OAuthError as exc:
        request.session.clear()
        raise AppError(
            "Identity verification failed. Start sign-in again.", "authentication_failed", 401
        ) from exc
    request.session.clear()
    raw = secrets.token_urlsafe(32)
    with runtime.database.sessions.begin() as session:
        user = session.scalar(
            select(User).where(User.issuer == claims["iss"], User.subject == claims["sub"])
        )
        if user is None:
            user = User(
                issuer=claims["iss"],
                subject=claims["sub"],
                display_name=str(claims.get("name", ""))[:120],
                email=str(claims["email"])[:320] if claims.get("email") else None,
            )
            session.add(user)
            session.flush()
        if user.status != "ACTIVE":
            raise AppError("This identity is disabled", "authentication_failed", 401)
        user.last_seen_at = datetime.now(timezone.utc)
        # Replace an existing application session, avoiding session fixation.
        old = request.cookies.get(COOKIE)
        if old:
            session.execute(
                delete(LoginSession).where(LoginSession.token_hash == digest_token(old))
            )
        session.add(
            LoginSession(
                token_hash=digest_token(raw),
                user_id=user.id,
                csrf_token=secrets.token_hex(32),
                expires_at=datetime.now(timezone.utc)
                + timedelta(hours=runtime.settings.session_hours),
            )
        )
        session.add(
            AuditEvent(
                event_type="SESSION_ESTABLISHED",
                entity_type="user",
                entity_id=user.id,
                actor="user",
                user_id=user.id,
                request_id=request.state.request_id,
                metadata_json={},
            )
        )
    response = RedirectResponse(runtime.settings.frontend_url, status_code=303)
    response.set_cookie(
        COOKIE,
        raw,
        httponly=True,
        secure=runtime.settings.app_env == "production",
        samesite="lax",
        max_age=runtime.settings.session_hours * 3600,
        path="/",
    )
    return response


@router.get("/me")
def me(request: Request):
    runtime = request.app.state.runtime
    if runtime.settings.auth_mode == "development":
        from ...db.models import DEFAULT_ORGANIZATION_ID

        return {
            "mode": "development",
            "user": None,
            "csrf_token": None,  # nosec B105
            "organizations": [
                {
                    "id": str(DEFAULT_ORGANIZATION_ID),
                    "name": "Development workspace",
                    "role": "OWNER",
                }
            ],
        }
    with runtime.database.sessions() as session:
        login = session.get(LoginSession, digest_token(request.cookies.get(COOKIE, "")))
        if login is None or login.expires_at <= datetime.now(timezone.utc):
            return JSONResponse(
                {"mode": "oidc", "user": None, "organizations": [], "csrf_token": None},  # nosec B105
                status_code=401,
            )
        user = session.get(User, login.user_id)
        if user is None or user.status != "ACTIVE":
            raise AppError("Sign in to continue", "authentication_required", 401)
        memberships = session.execute(
            select(Organization, OrganizationMembership)
            .join(OrganizationMembership)
            .where(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.status == "ACTIVE",
                Organization.status == "ACTIVE",
            )
            .order_by(Organization.name)
        ).all()
        return {
            "mode": "oidc",
            "user": {"id": str(user.id), "display_name": user.display_name, "email": user.email},
            "csrf_token": login.csrf_token,
            "organizations": [
                {
                    "id": str(org.id),
                    "name": org.name,
                    "role": member.role,
                    "retention": org.retention_policy,
                }
                for org, member in memberships
            ],
        }


@router.post("/logout")
def logout(request: Request):
    runtime = request.app.state.runtime
    with runtime.database.sessions.begin() as session:
        login = session.get(LoginSession, digest_token(request.cookies.get(COOKIE, "")))
        if login:
            import hmac

            if request.headers.get("Origin") not in {
                *runtime.settings.cors_origins,
                runtime.settings.frontend_url,
            } or not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), login.csrf_token):
                raise AppError("Request security check failed", "csrf_rejected", 403)
            session.add(
                AuditEvent(
                    event_type="SESSION_ENDED",
                    entity_type="user",
                    entity_id=login.user_id,
                    actor="user",
                    user_id=login.user_id,
                    request_id=request.state.request_id,
                    metadata_json={},
                )
            )
            session.delete(login)
    request.session.clear()
    response = JSONResponse({"signed_out": True})
    response.delete_cookie(
        COOKIE,
        path="/",
        httponly=True,
        secure=runtime.settings.app_env == "production",
        samesite="lax",
    )
    return response
