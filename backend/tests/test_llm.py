import asyncio
from types import SimpleNamespace

from app.services import llm, tracing


def _chunk(content):
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=content))])


def test_stream_text_sends_settings_and_yields_text(monkeypatch):
    calls = {}

    async def fake_acompletion(**kwargs):
        calls.update(kwargs)

        async def chunks():
            for content in ["Once ", None, "upon"]:  # thinking-only chunks have no content
                yield _chunk(content)

        return chunks()

    monkeypatch.setattr(llm.load_litellm(), "acompletion", fake_acompletion)
    monkeypatch.setenv("LLM_MODEL", "anthropic/claude-opus-5-5")
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")

    async def collect():
        return [text async for text in llm.stream_text([{"role": "user", "content": "hi"}])]

    assert asyncio.run(collect()) == ["Once ", "upon"]
    assert calls["model"] == "anthropic/claude-opus-5-5"
    assert calls["stream"] is True
    assert calls["reasoning_effort"] == "low"
    assert "temperature" not in calls


def test_complete_json_asks_for_the_schema_and_reads_the_reply(monkeypatch):
    calls = {}

    async def fake_acompletion(**kwargs):
        calls.update(kwargs)
        message = SimpleNamespace(content='{"scariness": 1}')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(llm.load_litellm(), "acompletion", fake_acompletion)
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    schema = {"type": "object", "properties": {"scariness": {"type": "integer"}}}

    reply = asyncio.run(llm.complete_json([{"role": "user", "content": "hi"}], schema, name="review"))
    assert reply == {"scariness": 1}
    assert calls["response_format"]["json_schema"]["schema"] == schema
    assert calls["reasoning_effort"] == "low"
    assert "stream" not in calls and "temperature" not in calls


def test_complete_with_tools_reads_tool_calls(monkeypatch):
    calls = {}

    def tool_call(id, name, arguments):
        return SimpleNamespace(id=id, function=SimpleNamespace(name=name, arguments=arguments))

    async def fake_acompletion(**kwargs):
        calls.update(kwargs)
        message = SimpleNamespace(
            content="Let me look at the cast.",
            tool_calls=[tool_call("a", "list_characters", "{}"), tool_call("b", "write_chapter", "{oops")],
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(llm.load_litellm(), "acompletion", fake_acompletion)
    tools = [{"type": "function", "function": {"name": "list_characters", "parameters": {"type": "object"}}}]

    turn = asyncio.run(llm.complete_with_tools([{"role": "user", "content": "hi"}], tools))
    assert turn.text == "Let me look at the cast."
    assert [(c.id, c.name, c.arguments) for c in turn.tool_calls] == [
        ("a", "list_characters", {}),
        ("b", "write_chapter", {"_invalid": "{oops"}),
    ]
    assert turn.message["role"] == "assistant"
    assert calls["tools"] == tools
    assert "tool_choice" not in calls and "temperature" not in calls


def test_each_model_call_sends_its_trace_as_metadata(monkeypatch):
    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        message = SimpleNamespace(content='{"ok": true}', tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(llm.load_litellm(), "acompletion", fake_acompletion)
    trace = tracing.Trace("story", details={"story_id": 1})
    asyncio.run(llm.complete_json([], {}, name="x", trace=trace.at("safety-check")))
    asyncio.run(llm.complete_json([], {}, name="x"))
    assert calls[0]["metadata"]["generation_name"] == "safety-check"
    assert calls[0]["metadata"]["trace_metadata"] == {"story_id": 1}
    assert "metadata" not in calls[1]


def test_app_starts_without_importing_litellm():
    """LiteLLM is slow to import, so the app must not load it until a story is written."""
    import subprocess
    import sys

    code = "import sys, app.main; print('litellm' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "False"


def test_the_lambda_build_keeps_everything_a_real_request_imports(monkeypatch):
    """The Lambda build deletes parts of LiteLLM to stay under 250 MB. Build each kind of request
    the app makes (stream, JSON schema, tools) for real, stopping just before it's sent, and check
    nothing it imported is in a deleted folder. Deleting a used folder once broke the live safety check."""
    import importlib.util
    import pathlib
    import sys

    import httpx

    bundle_file = pathlib.Path(__file__).resolve().parents[2] / "infra" / "stacks" / "bundle.py"
    spec = importlib.util.spec_from_file_location("bundle", bundle_file)
    bundle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bundle)

    class NotSent(Exception):
        pass

    async def refuse(self, request, **kwargs):
        raise NotSent()

    monkeypatch.setattr(httpx.AsyncClient, "send", refuse)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    litellm = llm.load_litellm()
    messages = [{"role": "user", "content": "hi"}]
    schema = {"type": "object", "properties": {}, "additionalProperties": False}
    tool = {"type": "function", "function": {"name": "f", "parameters": {"type": "object", "properties": {}}}}

    async def attempt(**kwargs):
        try:
            response = await litellm.acompletion(
                model="anthropic/claude-opus-5-5", messages=messages, max_tokens=5, num_retries=0, **kwargs
            )
            if kwargs.get("stream"):
                async for _ in response:
                    pass
        except Exception:
            pass  # expected: the request is never sent

    asyncio.run(attempt(stream=True))
    asyncio.run(attempt(response_format={"type": "json_schema", "json_schema": {"name": "x", "schema": schema, "strict": True}}))
    asyncio.run(attempt(tools=[tool]))

    removed = [p.replace("/", ".") for p in bundle.UNUSED_PATHS]
    used = sorted(m for m in sys.modules if any(m == r or m.startswith(r + ".") for r in removed))
    assert used == [], f"The Lambda build deletes modules a request needs: {used}"
