from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from ..config import Settings


class Database:
    def __init__(self, settings: Settings):
        self.engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={"connect_timeout": 3},
            pool_size=5,
            max_overflow=5,
            pool_timeout=10,
            pool_recycle=1800,
        )

        @event.listens_for(self.engine, "connect")
        def configure_timeouts(connection, record):
            with connection.cursor() as cursor:
                cursor.execute("SET statement_timeout TO '5s'")
                cursor.execute("SET lock_timeout TO '2s'")
                cursor.execute("SET idle_in_transaction_session_timeout TO '15s'")
            connection.commit()

        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def ready(self):
        with self.engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            if revision != "0005_identity_tenancy":
                raise RuntimeError("Database migration is required")
            connection.execute(text("SELECT id FROM generation_jobs LIMIT 0"))

    def dispose(self):
        self.engine.dispose()
