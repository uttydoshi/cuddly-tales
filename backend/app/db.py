"""Database engine and per-request sessions."""

from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
BASELINE_REVISION = "0001"
# Any fixed number: Postgres advisory locks are keyed by an integer.
MIGRATION_LOCK_ID = 7_310_524


def normalize_url(database_url: str) -> str:
    """Accept Postgres URLs as hosts like Neon give them (postgres:// or postgresql://)
    and use the psycopg 3 driver for them."""
    for prefix in ("postgres://", "postgresql://"):
        if database_url.startswith(prefix):
            return "postgresql+psycopg://" + database_url.removeprefix(prefix)
    return database_url


def make_engine(database_url: str) -> Engine:
    url = normalize_url(database_url)
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    # Postgres from Lambda: a small pool (one request at a time per instance, plus the
    # stream's save), checked before use because Neon closes idle connections.
    return create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=2, pool_recycle=300)


def migrate(engine: Engine) -> None:
    """Bring the database up to the latest migration. Runs at every app start.

    On Postgres an advisory lock makes concurrent starts (several Lambdas waking
    at once) wait for each other instead of racing. A database made before
    migrations existed (tables but no alembic_version) is marked as being at the
    first revision, then upgraded as normal.
    """
    from alembic import command
    from alembic.config import Config

    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": MIGRATION_LOCK_ID})
        config.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names())
        if "story" in tables and "alembic_version" not in tables:
            command.stamp(config, BASELINE_REVISION)
        command.upgrade(config, "head")



def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session
