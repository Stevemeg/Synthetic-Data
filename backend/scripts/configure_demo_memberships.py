"""Local-only operator assignment after each fake Keycloak user has signed in."""

from dotenv import load_dotenv
from sqlalchemy import select

from backend.app.config import ROOT, Settings
from backend.app.db.models import (
    DEFAULT_ORGANIZATION_ID,
    Organization,
    OrganizationMembership,
    User,
)
from backend.app.db.repositories.catalog import AuditRepository
from backend.app.db.session import Database


def main():
    load_dotenv(ROOT / ".env")
    settings = Settings.from_env()
    issuer = "http://127.0.0.1:8180/realms/medsynth-development"
    if settings.app_env != "development":
        raise SystemExit("Development fixture assignment only")
    database = Database(settings)
    try:
        with database.sessions.begin() as session:
            org = session.scalar(
                select(Organization).where(Organization.slug == "demo-second-organization")
            )
            if org is None:
                org = Organization(
                    name="Demo secondary research organization", slug="demo-second-organization"
                )
                session.add(org)
                session.flush()
            users = list(session.scalars(select(User).where(User.issuer == issuer)))
            for user in users:
                if user.display_name == "Demo Researcher A":
                    assignments = [(DEFAULT_ORGANIZATION_ID, "OWNER"), (org.id, "VIEWER")]
                elif user.display_name == "Demo Researcher B":
                    assignments = [(org.id, "OWNER")]
                elif user.display_name == "Demo Viewer":
                    assignments = [(DEFAULT_ORGANIZATION_ID, "VIEWER")]
                else:
                    continue
                for org_id, role in assignments:
                    member = session.scalar(
                        select(OrganizationMembership).where(
                            OrganizationMembership.organization_id == org_id,
                            OrganizationMembership.user_id == user.id,
                        )
                    )
                    if member is None:
                        member = OrganizationMembership(
                            organization_id=org_id, user_id=user.id, role=role
                        )
                        session.add(member)
                        session.flush()
                        session.info["organization_id"] = org_id
                        AuditRepository(session).record(
                            "DEMO_MEMBERSHIP_ASSIGNED",
                            "membership",
                            member.id,
                            actor="system",
                            metadata={"role": role},
                        )
        print("Assigned memberships for signed-in local fake identities only.")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
