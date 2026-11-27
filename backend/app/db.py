"""Database engine and per-request sessions."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine


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


def create_tables(engine: Engine) -> None:
    # Import models so their tables are registered before create_all.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session
