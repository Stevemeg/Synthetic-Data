from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from ...core.errors import AppError
from ...db.models import Organization, OrganizationMembership, User
from ...db.repositories.catalog import AuditRepository
from ...security.auth import authenticate
from ..dependencies import SessionDep

router = APIRouter(prefix="/api/v1/organization", tags=["Organization"])


class MembershipChange(BaseModel):
    role: Literal["OWNER", "EDITOR", "VIEWER"]
    status: Literal["ACTIVE", "REMOVED"] = "ACTIVE"


@router.get("/members")
def members(request: Request, session: SessionDep):
    principal = authenticate(request)
    if principal.role != "OWNER":
        raise AppError(
            "Only organization owners may view membership details", "permission_denied", 403
        )
    rows = session.execute(
        select(OrganizationMembership, User)
        .join(User)
        .where(
            OrganizationMembership.organization_id == principal.organization_id,
            OrganizationMembership.status == "ACTIVE",
        )
        .order_by(User.display_name)
        .limit(100)
    ).all()
    return [
        {
            "id": str(m.id),
            "user_id": str(u.id),
            "display_name": u.display_name,
            "email": u.email,
            "role": m.role,
        }
        for m, u in rows
    ]


@router.patch("/members/{membership_id}")
def change_member(
    membership_id: UUID, change: MembershipChange, request: Request, session: SessionDep
):
    principal = authenticate(request)
    with session.begin():
        session.scalar(
            select(Organization)
            .where(Organization.id == principal.organization_id)
            .with_for_update()
        )
        member = session.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.id == membership_id,
                OrganizationMembership.organization_id == principal.organization_id,
            )
        )
        if member is None:
            raise AppError("Membership not found", "not_found", 404)
        owners = session.scalar(
            select(func.count())
            .select_from(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == principal.organization_id,
                OrganizationMembership.status == "ACTIVE",
                OrganizationMembership.role == "OWNER",
            )
        )
        if (
            member.role == "OWNER"
            and member.status == "ACTIVE"
            and owners == 1
            and (change.role != "OWNER" or change.status != "ACTIVE")
        ):
            raise AppError("An organization must retain an active owner", "last_owner", 409)
        member.role, member.status = change.role, change.status
        AuditRepository(session).record(
            "MEMBERSHIP_CHANGED",
            "membership",
            member.id,
            metadata={"role": change.role, "status": change.status},
        )
    return {"updated": True}
