"""Create missing local fixture secrets; preserve existing settings and never print secrets."""

import os
import secrets

from dotenv import dotenv_values
from sqlalchemy.engine import URL

from backend.app.config import ROOT


def main():
    if os.getenv("APP_ENV", "development") != "development":
        raise SystemExit("This bootstrap is development-only")
    path = ROOT / ".env"
    if not path.exists():
        path.write_text((ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
    current = dict(dotenv_values(path))
    supplied = {}
    for name in (
        "POSTGRES_PASSWORD",
        "OIDC_DEV_ADMIN_PASSWORD",
        "S3_ACCESS_KEY",
        "S3_SECRET_KEY",
        "SESSION_SECRET",
        "METRICS_TOKEN",
    ):
        if not current.get(name):
            supplied[name] = secrets.token_urlsafe(32)
    merged = {**current, **supplied}
    if not current.get("S3_BUCKET"):
        supplied["S3_BUCKET"] = "medsynth-development"
    if not current.get("CONTAINER_DATABASE_URL"):
        supplied["CONTAINER_DATABASE_URL"] = URL.create(
            "postgresql+psycopg",
            username=merged.get("POSTGRES_USER") or "medsynth",
            password=merged["POSTGRES_PASSWORD"],
            host="postgres",
            port=5432,
            database=merged.get("POSTGRES_DB") or "medsynth",
        ).render_as_string(hide_password=False)
    with path.open("a", encoding="utf-8") as output:
        for name, value in supplied.items():
            output.write(f"\n{name}={value}\n")
    print(
        f"Prepared {len(supplied)} missing development settings in ignored .env. No secrets displayed."
    )


if __name__ == "__main__":
    main()
