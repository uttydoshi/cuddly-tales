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
    assert calls["output_format"] == {"type": "json_schema", "schema": schema}  # Claude: native structured output
    assert "response_format" not in calls and "tool_choice" not in calls
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


def test_structured_output_is_native_for_claude_and_generic_elsewhere():
    schema = {"type": "object"}
    assert llm.structured_output("anthropic/claude-opus-5-5", "review", schema) == {
        "output_format": {"type": "json_schema", "schema": schema}
    }
    generic = llm.structured_output("openai/gpt-x", "review", schema)
    assert generic["response_format"]["json_schema"] == {"name": "review", "schema": schema, "strict": True}


def test_the_safety_check_request_never_forces_a_tool(monkeypatch):
    """Current Claude models reject a forced tool call ("tool_choice ... not supported"). Build the
    safety check's request for real, stop it before it's sent, and look at what would have gone."""
    import json as json_module

    import httpx

    sent = []

    class NotSent(Exception):
        pass

    async def capture(self, request, **kwargs):
        sent.append(json_module.loads(request.content))
        raise NotSent()

    monkeypatch.setattr(httpx.AsyncClient, "send", capture)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setenv("LLM_MODEL", "anthropic/claude-opus-5-5")
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}
    try:
        asyncio.run(llm.complete_json([{"role": "user", "content": "hi"}], schema, name="review"))
    except Exception:
        pass
    assert sent, "the request was never built"
    body = sent[0]
    assert "tool_choice" not in body and "tools" not in body
    assert body["output_format"]["schema"]["properties"] == {"ok": {"type": "boolean"}}


def test_missing_model_prices_are_registered(monkeypatch):
    registered = {}
    fake = SimpleNamespace(model_cost={"claude-sonnet-x": {}}, register_model=registered.update)
    llm._register_missing_prices(fake)
    assert registered["claude-opus-5-5"]["input_cost_per_token"] == 4e-06
    already = SimpleNamespace(model_cost={"claude-opus-5-5": {}}, register_model=registered.clear)
    llm._register_missing_prices(already)  # known already: left alone
    assert registered


def test_traces_reach_the_exporter_as_one_trace_before_flush_returns(monkeypatch):
    """Real LiteLLM calls with tracing on, and the OpenTelemetry export caught instead of sent:
    both calls of one story must be one trace, exported by the time flush() returns (on Lambda
    nothing runs after the response ends)."""
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import SpanExportResult

    exported = []

    def catch(self, spans):
        exported.extend(spans)
        return SpanExportResult.SUCCESS

    monkeypatch.setattr(OTLPSpanExporter, "export", catch)
    llm.load_litellm()
    from litellm.litellm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER as worker

    asyncio.run(worker.flush())  # earlier tests' queued logging runs now, before tracing is on
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://127.0.0.1:9")  # never reached: export is caught
    litellm = llm.load_litellm()
    # LiteLLM reads the keys once, when it first makes its Langfuse logger, and keeps that logger
    # for the process (on Lambda the keys are loaded before LiteLLM). Start this test with none,
    # and put LiteLLM's lists back afterwards.
    from litellm.litellm_core_utils import litellm_logging

    monkeypatch.setattr(litellm_logging, "_in_memory_loggers", [])
    for name in ("callbacks", "success_callback", "failure_callback", "_async_success_callback", "_async_failure_callback"):
        monkeypatch.setattr(litellm, name, [c for c in getattr(litellm, name) if not hasattr(c, "_tracer_provider")])
    tracing.setup(litellm)
    trace = tracing.Trace("story", details={"story_id": 7})

    async def story():
        for step in ("write", "safety-check"):
            await litellm.acompletion(
                model="anthropic/claude-opus-5-5",
                messages=[{"role": "user", "content": "hi"}],
                mock_response="Once upon a time.",
                metadata=trace.at(step).metadata(),
            )
        await tracing.flush()

    asyncio.run(story())
    ours = [s for s in exported if s.context.trace_id == int(trace.id, 16)]
    assert len(ours) >= 2, f"expected both calls in trace {trace.id}, got {[(s.name, hex(s.context.trace_id)) for s in exported]}"
    steps = {str(value) for span in ours for value in span.attributes.values()}
    assert {"write", "safety-check"} <= steps
    for provider in tracing._span_providers():  # this test's logger: close it now, not at exit
        provider.shutdown()
