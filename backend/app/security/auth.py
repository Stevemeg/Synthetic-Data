"""Opaque, revocable application sessions; provider tokens never enter the browser."""

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Request
from sqlalchemy import select

from ..core.errors import AppError
from ..db.models import (
    DEFAULT_ORGANIZATION_ID,
    LoginSession,
    Organization,
    OrganizationMembership,
    User,
)

COOKIE = "medsynth_session"
ROLES = {"VIEWER": 0, "EDITOR": 1, "OWNER": 2}


def digest_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class Principal:
    user_id: UUID | None
    organization_id: UUID
    role: str
    csrf_token: str | None = None
    token_hash: str | None = None


def authenticate(request: Request) -> Principal:
    if hasattr(request.state, "principal"):
        return request.state.principal
    runtime = request.app.state.runtime
    if runtime.settings.auth_mode == "development":
        # Deliberate local bypass, never accepted by production startup validation.
        principal = Principal(None, DEFAULT_ORGANIZATION_ID, "OWNER")
    else:
        cookie = request.cookies.get(COOKIE, "")
        if not cookie or len(cookie) > 128:
            raise AppError("Sign in to continue", "authentication_required", 401)
        with runtime.database.sessions() as session:
            login = session.get(LoginSession, digest_token(cookie))
            if login is None or login.expires_at <= datetime.now(timezone.utc):
                raise AppError(
                    "Your session has expired. Sign in again.", "authentication_required", 401
                )
            user = session.get(User, login.user_id)
            if user is None or user.status != "ACTIVE":
                raise AppError("Sign in to continue", "authentication_required", 401)
            query = (
                select(OrganizationMembership)
                .join(Organization)
                .where(
                    OrganizationMembership.user_id == user.id,
                    OrganizationMembership.status == "ACTIVE",
                    Organization.status == "ACTIVE",
                )
                .order_by(OrganizationMembership.organization_id)
            )
            selected = request.headers.get("X-Organization-ID")
            if selected:
                try:
                    query = query.where(OrganizationMembership.organization_id == UUID(selected))
                except ValueError as exc:
                    raise AppError("Organization not found", "not_found", 404) from exc
            member = session.scalar(query)
            if member is None:
                raise AppError(
                    "No organization access is assigned. Contact your organization owner.",
                    "organization_access_required",
                    403,
                )
            principal = Principal(
                user.id, member.organization_id, member.role, login.csrf_token, login.token_hash
            )
    request.state.principal = principal
    return principal


def csrf_check(request: Request, principal: Principal):
    if principal.csrf_token is None:
        return
    supplied = request.headers.get("X-CSRF-Token", "")
    origin = request.headers.get("Origin", "")
    settings = request.app.state.runtime.settings
    if origin not in {*settings.cors_origins, settings.frontend_url} or not hmac.compare_digest(
        supplied, principal.csrf_token
    ):
        raise AppError(
            "Request security check failed. Refresh the workspace and try again.",
            "csrf_rejected",
            403,
        )


def require_access(request: Request) -> Principal:
    principal = authenticate(request)
    if getattr(request.state, "access_checked", False):
        return principal
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf_check(request, principal)
        minimum = "EDITOR"
        path = request.url.path
        if path.endswith("/compare"):
            minimum = "VIEWER"
        elif (
            "release-policies" in path
            or request.method == "PATCH"
            and "/projects/" in path
            or path.endswith("/deletion")
            or "/members" in path
        ):
            minimum = "OWNER"
        if ROLES[principal.role] < ROLES[minimum]:
            raise AppError(
                "Your organization role does not permit this action", "permission_denied", 403
            )
        if request.method == "POST" and not path.endswith("/compare"):
            from .abuse import submission_limit

            if principal.user_id is not None:
                submission_limit(principal)
    request.state.access_checked = True
    return principal
