"""Identify old unreferenced storage files; default is a count-only dry run."""

import argparse
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import select

from backend.app.config import ROOT, Settings
from backend.app.core.errors import AppError
from backend.app.db.models import Artifact, Dataset
from backend.app.db.session import Database
from backend.app.storage.local import LocalArtifactStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--min-age-hours", type=int, default=24)
    args = parser.parse_args()
    if args.min_age_hours < 24:
        parser.error("Safety age must be at least 24 hours")
    load_dotenv(ROOT / ".env")
    settings = Settings.from_env()
    database = Database(settings)
    store = LocalArtifactStore(settings.artifact_storage_path)
    try:
        database.ready()
        with database.sessions() as session:
            references = set(session.scalars(select(Dataset.storage_key))) | set(
                session.scalars(select(Artifact.storage_key))
            )
        cutoff = datetime.now(timezone.utc).timestamp() - args.min_age_hours * 3600
        candidates = []
        for file in store.root.rglob("*"):
            if file.is_symlink() or not file.is_file() or file.stat().st_mtime > cutoff:
                continue
            key = file.relative_to(store.root).as_posix()
            try:
                store.path(key)
            except AppError:
                continue  # Abandoned internal write temporaries require operator inspection.
            if key not in references:
                candidates.append(key)
        if args.apply:
            # Stop API/workers before --apply: no cross-resource transaction spans the scan.
            for key in candidates:
                store.delete(key)
        print(
            f"Old unreferenced objects: {len(candidates)}; deleted: {len(candidates) if args.apply else 0}"
        )
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
