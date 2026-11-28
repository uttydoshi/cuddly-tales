from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from app.main import create_app
from app.services import llm


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


@pytest.fixture(autouse=True)
def no_real_model(request, monkeypatch):
    """Tests never call the real model (cost, speed, flakiness). A test that needs the model
    replaces these with a fake; anything that reaches them unfaked fails like a provider outage.
    test_llm.py tests these functions themselves, with LiteLLM faked instead."""
    if request.module.__name__.endswith("test_llm"):
        return

    async def stream_text(messages, **kwargs):
        raise RuntimeError("tests must fake llm.stream_text")
        yield  # pragma: no cover  (makes this an async generator)

    async def complete_json(messages, schema, **kwargs):
        raise RuntimeError("tests must fake llm.complete_json")

    async def complete_with_tools(messages, tools, **kwargs):
        raise RuntimeError("tests must fake llm.complete_with_tools")

    monkeypatch.setattr(llm, "stream_text", stream_text)
    monkeypatch.setattr(llm, "complete_json", complete_json)
    monkeypatch.setattr(llm, "complete_with_tools", complete_with_tools)
