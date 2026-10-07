from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.app.config import Settings


@pytest.fixture
def settings(tmp_path):
    return replace(
        Settings.from_env({}),
        app_env="test",
        generated_dir=tmp_path / "generated",
        upload_dir=tmp_path / "uploads",
        model_dir=tmp_path / "models",
        ecg_epochs=1,
        artifact_storage_path=tmp_path / "artifacts",
        database_url="postgresql+psycopg://nobody@127.0.0.1:1/missing",
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def pg_settings(settings):
    """Real PostgreSQL, isolated schema; never touch the development schema."""
    import os
    from uuid import uuid4

    from alembic import command
    from alembic.config import Config
    from dotenv import dotenv_values
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.schema import CreateSchema, DropSchema

    from backend.app.config import ROOT

    env = {**dotenv_values(ROOT / ".env"), **os.environ}
    url = make_url(env.get("TEST_DATABASE_URL") or Settings.from_env(env).database_url)
    admin = create_engine(url, hide_parameters=True)
    schema = "ms_test_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    query = dict(url.query)
    query["options"] = "-csearch_path=" + schema
    isolated = url.set(query=query)
    result = replace(settings, database_url=isolated.render_as_string(hide_password=False))
    engine = create_engine(isolated, hide_parameters=True)
    try:
        config = Config(str(ROOT / "alembic.ini"))
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield result
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.fixture
def pg_client(pg_settings):
    with TestClient(create_app(pg_settings), raise_server_exceptions=False) as client:
        yield client
