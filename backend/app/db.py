"""Database engine and per-request sessions."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine


def make_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def create_tables(engine: Engine) -> None:
    # Import models so their tables are registered before create_all.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session
