"""Langfuse tracing: on only with real keys, and every model call says where it belongs."""

import asyncio
import json
import os
from types import SimpleNamespace

import pytest

from app import aws_secrets
from app.services import llm, safety, tracing

REAL_KEYS = {"LANGFUSE_PUBLIC_KEY": "pk-lf-1234", "LANGFUSE_SECRET_KEY": "sk-lf-5678"}


@pytest.mark.parametrize(
    ("public", "secret", "on"),
    [
        ("pk-lf-1234", "sk-lf-5678", True),
        ("", "", False),
        ("pk-lf-your-public-key", "sk-lf-your-secret-key", False),  # .env.example's placeholders
        ("pk-lf-1234", "", False),
    ],
)
def test_tracing_is_on_only_with_real_keys(monkeypatch, public, secret, on):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", public)
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", secret)
    assert tracing.enabled() is on


def test_trace_metadata_names_the_feature_step_and_place(monkeypatch):
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "cuddly-tales-api")
    trace = tracing.Trace("adventure-agent", details={"run_id": 3}).in_session("adventure-7").at("agent-turn-2")
    assert trace.metadata() == {
        "trace_id": trace.id,
        "trace_name": "adventure-agent",
        "generation_name": "agent-turn-2",
        "tags": ["adventure-agent", "live"],
        "trace_metadata": {"run_id": 3},
        "session_id": "live-adventure-7",
    }
    assert len(trace.id) == 32  # unique, so local and live traces never merge


def test_with_keys_every_call_in_a_trace_shares_one_opentelemetry_parent(monkeypatch):
    for name, value in REAL_KEYS.items():
        monkeypatch.setenv(name, value)
    trace = tracing.Trace("story")
    write, check = trace.at("write").metadata(), trace.at("safety-check").metadata()
    parent = write["litellm_parent_otel_span"].get_span_context()
    assert parent.trace_id == int(trace.id, 16)  # Langfuse groups by this
    assert check["litellm_parent_otel_span"].get_span_context() == parent
    assert tracing.Trace("story").metadata()["litellm_parent_otel_span"].get_span_context().trace_id != parent.trace_id


def test_the_root_span_names_the_trace_and_ends_with_flush(monkeypatch):
    for name, value in REAL_KEYS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(tracing, "integration_available", lambda: True)
    trace = tracing.Trace("adventure-agent", details={"run_id": 4})
    root = tracing.root_span(trace.at("agent-turn-1"))
    assert root.name == "adventure-agent"
    assert root.attributes["langfuse.trace.tags"] == ("adventure-agent", "local")  # a real list, not text
    assert root.attributes["langfuse.trace.metadata.run_id"] == "4"
    assert root.parent is None  # the trace's root: Langfuse lists traces by their root
    later = trace.in_session("adventure-9")
    assert tracing.root_span(later) is root
    assert root.attributes["session.id"] == "local-adventure-9"
    tracing._end_root(later)
    assert root.end_time is not None and trace.id not in tracing._roots


def test_content_can_be_kept_out_of_langfuse(monkeypatch):
    monkeypatch.setenv("LANGFUSE_LOG_CONTENT", "false")
    metadata = tracing.Trace("story").metadata()
    assert metadata["mask_input"] is True and metadata["mask_output"] is True
    assert metadata["tags"] == ["story", "local"]


def test_setup_adds_the_langfuse_callback_once_and_only_with_keys(monkeypatch):
    monkeypatch.setattr(tracing, "integration_available", lambda: True)
    fake = SimpleNamespace(callbacks=[])
    tracing.setup(fake)
    assert fake.callbacks == []
    for name, value in REAL_KEYS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("LANGFUSE_TRACING_ENVIRONMENT", raising=False)
    monkeypatch.delenv("OTEL_ENVIRONMENT_NAME", raising=False)
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "cuddly-tales-api")
    tracing.setup(fake)
    tracing.setup(fake)
    assert fake.callbacks == ["langfuse_otel"]
    assert os.environ["LANGFUSE_TRACING_ENVIRONMENT"] == "live"  # Langfuse's environment filter
    assert os.environ["OTEL_ENVIRONMENT_NAME"] == "live"


def test_tracing_stays_off_if_anything_it_needs_is_missing(monkeypatch):
    for name, value in REAL_KEYS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(tracing, "NEEDED", ("litellm.integrations.no_such_module",))
    fake = SimpleNamespace(callbacks=[])
    tracing.setup(fake)
    assert fake.callbacks == []
    asyncio.run(tracing.flush())  # and flushing is a no-op, not an error


def test_flush_does_nothing_without_keys():
    asyncio.run(tracing.flush())  # no keys: returns without loading or sending anything


def test_a_story_is_one_trace_with_its_check_and_rewrite(client, monkeypatch):
    traces, flushed = [], []

    async def stream_text(messages, trace=None, **kwargs):
        traces.append(trace)
        yield "# Minnie's Ball\n\n" + "Minnie chased the ball. " * 80

    attempts = iter([False, True])

    async def check_story(title, body, child, characters, *, bedtime, earlier=(), trace=None):
        traces.append(trace.at("safety-check"))
        passed = next(attempts)
        return safety.Attempt(passed=passed, word_count=1, scariness=1 if passed else 3, problems=[] if passed else ["x"])

    async def flush(trace=None):
        flushed.append(trace)

    monkeypatch.setattr(llm, "stream_text", stream_text)
    monkeypatch.setattr(safety, "check_story", check_story)
    monkeypatch.setattr(tracing, "flush", flush)
    minnie = next(c["id"] for c in client.get("/api/characters").json() if c["name"] == "Minnie")
    story_id = client.post("/api/stories", json={"character_ids": [minnie]}).json()["id"]
    client.get(f"/api/stories/{story_id}/stream")

    assert [t.step for t in traces] == ["write", "safety-check", "rewrite", "safety-check"]
    assert len({t.id for t in traces}) == 1
    assert traces[0].feature == "story" and traces[0].details["story_id"] == story_id
    assert [t.id for t in flushed] == [traces[0].id]  # the story's own trace is ended and sent


def test_an_agent_run_is_one_trace_in_its_adventures_session(client, monkeypatch):
    seen, flushed = [], []

    async def complete_with_tools(messages, tools, trace=None, **kwargs):
        seen.append(trace)
        return llm.AgentTurn(text="Done.", tool_calls=[], message={"role": "assistant", "content": "Done."})

    async def flush(trace=None):
        flushed.append(trace)

    monkeypatch.setattr(llm, "complete_with_tools", complete_with_tools)
    monkeypatch.setattr(tracing, "flush", flush)
    run = client.post("/api/adventures", json={"chapter_count": 3}).json()
    client.get(f"/api/agent-runs/{run['id']}/stream")

    assert seen[0].feature == "adventure-agent"
    assert seen[0].step == "agent-turn-1"
    assert seen[0].details["run_id"] == run["id"]
    assert [t.id for t in flushed] == [seen[0].id]


def test_langfuse_keys_come_from_an_optional_secret(monkeypatch):
    keys = {"public_key": "pk-lf-1", "secret_key": "sk-lf-2", "host": "https://us.cloud.langfuse.com"}
    monkeypatch.setattr(aws_secrets, "read_secret", lambda secret_id: json.dumps(keys))
    monkeypatch.setenv("LANGFUSE_KEYS_SECRET", "cuddly-tales/langfuse-keys")
    monkeypatch.delenv("LANGFUSE_HOST")  # the test setup points it at a closed port
    aws_secrets.load_into_env()

    assert os.environ["LANGFUSE_PUBLIC_KEY"] == "pk-lf-1"
    assert os.environ["LANGFUSE_HOST"] == "https://us.cloud.langfuse.com"


def test_a_missing_langfuse_secret_doesnt_stop_the_app(monkeypatch):
    def missing(secret_id):
        raise RuntimeError("ResourceNotFoundException")

    monkeypatch.setattr(aws_secrets, "read_secret", missing)
    monkeypatch.setenv("LANGFUSE_KEYS_SECRET", "cuddly-tales/langfuse-keys")
    aws_secrets.load_into_env()  # no error: tracing just stays off
    assert not tracing.enabled()
