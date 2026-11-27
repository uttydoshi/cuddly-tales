from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from app.main import create_app


@pytest.fixture
def engine():
    # One shared in-memory database per test.
    return create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )


@pytest.fixture
def client(engine) -> Iterator[TestClient]:
    with TestClient(create_app(engine)) as test_client:
        yield test_client
