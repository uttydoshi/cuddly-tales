import asyncio
from types import SimpleNamespace

from app.services import llm


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

    monkeypatch.setattr(llm.litellm, "acompletion", fake_acompletion)
    monkeypatch.setenv("LLM_MODEL", "anthropic/claude-opus-5-5")
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")

    async def collect():
        return [text async for text in llm.stream_text([{"role": "user", "content": "hi"}])]

    assert asyncio.run(collect()) == ["Once ", "upon"]
    assert calls["model"] == "anthropic/claude-opus-5-5"
    assert calls["stream"] is True
    assert calls["reasoning_effort"] == "low"
    assert "temperature" not in calls
