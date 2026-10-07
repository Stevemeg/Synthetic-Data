"""Development-only PostgreSQL round trip; never restore over an existing database."""

import argparse
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

TABLES = (
    "projects",
    "datasets",
    "generation_jobs",
    "evaluation_runs",
    "release_policies",
    "artifacts",
    "organizations",
    "organization_memberships",
    "users",
    "audit_events",
)


def command(container, *args, input_bytes=None):
    return subprocess.run(
        ["docker", "exec", "-i", container, *args],
        input=input_bytes,
        capture_output=True,
        check=True,
    ).stdout


def counts(container, database, user):
    return {
        table: int(
            command(
                container,
                "psql",
                "-U",
                user,
                "-d",
                database,
                "-Atc",
                f"SELECT count(*) FROM {table}",
            ).strip()
        )
        for table in TABLES
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="synthetic-data-postgres-1")
    parser.add_argument("--database", default="medsynth")
    parser.add_argument("--user", default="medsynth")
    parser.add_argument(
        "--verify-storage",
        action="store_true",
        help="Verify every active restored source/artifact against the configured store",
    )
    args = parser.parse_args()
    target = "ms_restore_" + uuid4().hex
    before = counts(args.container, args.database, args.user)
    backup = command(
        args.container,
        "pg_dump",
        "-U",
        args.user,
        "-d",
        args.database,
        "-Fc",
        "--no-owner",
        "--no-acl",
    )
    output = Path("backend/.work/backup-restore")
    output.mkdir(parents=True, exist_ok=True)
    (output / "development.dump").write_bytes(backup)
    command(args.container, "createdb", "-U", args.user, target)
    try:
        command(
            args.container,
            "pg_restore",
            "-U",
            args.user,
            "-d",
            target,
            "--no-owner",
            "--no-acl",
            "--exit-on-error",
            input_bytes=backup,
        )
        restored = counts(args.container, target, args.user)
        assert before == restored, "Backup/restore counts differ"
        result = {"passed": True, "counts": restored, "backup_bytes": len(backup), "target": target}
        if args.verify_storage:
            from dotenv import load_dotenv
            from sqlalchemy import select
            from sqlalchemy.engine import make_url

            from backend.app.config import ROOT, Settings
            from backend.app.db.models import Artifact, Dataset, GenerationJob, Project
            from backend.app.db.session import Database
            from backend.app.storage.factory import artifact_store

            load_dotenv(ROOT / ".env")
            settings = Settings.from_env()
            settings = replace(
                settings,
                database_url=make_url(settings.database_url)
                .set(database=target)
                .render_as_string(hide_password=False),
            )
            database = Database(settings)
            store = artifact_store(settings)
            verified = 0
            try:
                with database.sessions() as session:
                    sources = session.scalars(
                        select(Dataset).join(Project).where(Project.deletion_state == "ACTIVE")
                    ).all()
                    artifacts = session.scalars(
                        select(Artifact)
                        .join(GenerationJob)
                        .join(Project)
                        .where(Project.deletion_state == "ACTIVE")
                    ).all()
                for record in [*sources, *artifacts]:
                    metadata = store.metadata(record.storage_key)
                    assert (metadata.sha256, metadata.size_bytes) == (
                        record.sha256,
                        record.size_bytes,
                    ), "Restored object integrity differs"
                    verified += 1
                result["active_objects_verified"] = verified
            finally:
                database.dispose()
        (output / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result))
    finally:
        command(args.container, "dropdb", "-U", args.user, target)


if __name__ == "__main__":
    main()
