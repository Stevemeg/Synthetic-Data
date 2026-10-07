from alembic import context
from dotenv import load_dotenv

from backend.app.config import ROOT, Settings
from backend.app.db import models  # noqa: F401
from backend.app.db.base import Base
from backend.app.db.session import Database

load_dotenv(ROOT / ".env", override=False)
config = context.config


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=Settings.from_env().database_url, target_metadata=Base.metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    run(config.attributes["connection"])
else:
    database = Database(Settings.from_env())
    try:
        with database.engine.connect() as connection:
            run(connection)
    finally:
        database.dispose()
