"""Maintenance-window copy, SHA verification and reference update; originals retained."""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select

from backend.app.config import ROOT, Settings
from backend.app.db.models import Artifact, Dataset, GenerationJob, Project
from backend.app.db.session import Database
from backend.app.storage.local import LocalArtifactStore
from backend.app.storage.s3 import S3ArtifactStore


def migrate(database, local, remote, journal: Path):
    moved = 0
    for model in (Dataset, Artifact):
        with database.sessions() as session:
            query = select(model.id)
            if model is Dataset:
                query = query.join(Project, Dataset.project_id == Project.id)
            else:
                query = query.join(GenerationJob, Artifact.job_id == GenerationJob.id).join(
                    Project, GenerationJob.project_id == Project.id
                )
            # Tombstones must never republish bytes retained only in old backups.
            ids = list(session.scalars(query.where(Project.deletion_state == "ACTIVE")))
        for ident in ids:
            with database.sessions() as session:
                record = session.get(model, ident)
                old = record.storage_key
                if old.startswith("s3/"):
                    continue
                sha, size = record.sha256, record.size_bytes
            target = "s3/" + old
            actual = local.metadata(old)
            if (actual.sha256, actual.size_bytes) != (sha, size):
                raise ValueError("Local artifact integrity failed; migration stopped")
            if not remote.exists(target):
                with local.get(old) as source:
                    remote.put(target, source)
            actual = remote.metadata(target)
            if (actual.sha256, actual.size_bytes) != (sha, size):
                raise ValueError("Remote artifact integrity failed; reference not changed")
            # Write rollback information before changing the reference; contains no content/secrets.
            journal.parent.mkdir(parents=True, exist_ok=True)
            with journal.open("a", encoding="utf-8") as output:
                output.write(
                    json.dumps(
                        {
                            "table": model.__tablename__,
                            "id": str(ident),
                            "old": old,
                            "new": target,
                            "sha256": sha,
                        }
                    )
                    + "\n"
                )
                output.flush()
                os.fsync(output.fileno())
            with database.sessions.begin() as session:
                record = session.scalar(select(model).where(model.id == ident).with_for_update())
                if record.storage_key != old:
                    raise ValueError(
                        "Reference changed concurrently; stop API and workers before migration"
                    )
                record.storage_key = target
            moved += 1
    return moved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maintenance-window", action="store_true", required=True)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    settings = Settings.from_env()
    if not args.maintenance_window or not settings.s3_bucket:
        raise SystemExit("S3 configuration and an offline maintenance window are required")
    database = Database(settings)
    try:
        count = migrate(
            database,
            LocalArtifactStore(settings.artifact_storage_path),
            S3ArtifactStore(settings),
            ROOT / "backend/.work/storage-migration.jsonl",
        )
        print(
            f"Verified and migrated {count} references. Local originals retained for rollback. Set ARTIFACT_STORAGE_BACKEND=s3 before resuming services."
        )
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
