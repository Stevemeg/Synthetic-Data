"""Operator-only identity provisioning. No invitations or email-based identity matching."""

import argparse

from dotenv import load_dotenv
from sqlalchemy import select

from backend.app.config import ROOT, Settings
from backend.app.db.models import Organization, OrganizationMembership, User
from backend.app.db.repositories.catalog import AuditRepository
from backend.app.db.session import Database


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--organization", required=True, help="Organization slug")
    parser.add_argument("--name", help="Create an organization with this name if absent")
    parser.add_argument("--role", choices=["OWNER", "EDITOR", "VIEWER"], required=True)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    database = Database(Settings.from_env())
    try:
        with database.sessions.begin() as session:
            user = session.scalar(
                select(User).where(User.issuer == args.issuer, User.subject == args.subject)
            )
            if user is None:
                raise SystemExit("Identity must complete OIDC sign-in before assignment")
            org = session.scalar(
                select(Organization).where(Organization.slug == args.organization).with_for_update()
            )
            if org is None:
                if not args.name:
                    raise SystemExit("Organization absent; supply --name for creation")
                org = Organization(name=args.name, slug=args.organization)
                session.add(org)
                session.flush()
            member = session.scalar(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == org.id,
                    OrganizationMembership.user_id == user.id,
                )
            )
            if member is None:
                member = OrganizationMembership(
                    organization_id=org.id, user_id=user.id, role=args.role
                )
                session.add(member)
                session.flush()
            else:
                if member.role == "OWNER" and args.role != "OWNER":
                    raise SystemExit("Use the owner-authorized membership API to demote owners")
                member.role, member.status = args.role, "ACTIVE"
            session.info["organization_id"] = org.id
            AuditRepository(session).record(
                "MEMBERSHIP_ASSIGNED",
                "membership",
                member.id,
                actor="system",
                metadata={"role": args.role},
            )
        print("Membership assigned; operator action recorded in audit history.")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
