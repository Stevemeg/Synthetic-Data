"""Development migration verification with counts and parent relationships."""

import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import text

from backend.app.config import ROOT, Settings
from backend.app.db.session import Database

TABLES = (
    "projects",
    "datasets",
    "generation_jobs",
    "evaluation_runs",
    "release_policies",
    "artifacts",
    "audit_events",
)


def snapshot(connection):
    return {
        table: connection.execute(text(f"SELECT id FROM {table} ORDER BY id")).scalars().all()
        for table in TABLES
    }


def main():
    load_dotenv(ROOT / ".env")
    database = Database(Settings.from_env())
    try:
        with database.engine.connect() as connection:
            before = snapshot(connection)
        config = Config(str(ROOT / "alembic.ini"))
        with database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with database.engine.connect() as connection:
            after = snapshot(connection)
            assert before == after
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM projects WHERE organization_id <> '00000000-0000-4000-8000-000000000001'"
                    )
                )
                == 0
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM datasets d LEFT JOIN projects p ON p.id=d.project_id WHERE p.id IS NULL"
                    )
                )
                == 0
            )
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM audit_events WHERE organization_id IS NULL")
                )
                == 0
            )
        result = {
            "preserved": True,
            "counts": {t: len(ids) for t, ids in after.items()},
            "revision": "0005_identity_tenancy",
        }
        output = Path(ROOT / "backend/.work/phase6-migration.json")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result))
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
