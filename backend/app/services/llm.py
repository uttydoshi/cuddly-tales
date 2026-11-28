"""The only place that talks to LiteLLM. Swap this out (or monkeypatch it) in tests."""

import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from types import ModuleType

from app.config import get_settings
from app.services import tracing
from app.services.tracing import Trace


def load_litellm() -> ModuleType:
    """Import LiteLLM on first use, not at app start.

    LiteLLM takes seconds to import, and Lambda allows 10 seconds for the app to
    start. Loading it here keeps start-up fast; only the first story pays for it.
    Its built-in price list is used, so it doesn't download one from GitHub.
    """
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    import litellm

    tracing.setup(litellm)
    return litellm


def _traced(trace: Trace | None) -> dict:
    """The call's place in Langfuse (see tracing.py), as LiteLLM metadata."""
    return {"metadata": trace.metadata()} if trace else {}


async def stream_text(
    messages: list[dict], *, max_tokens: int = 4000, trace: Trace | None = None
) -> AsyncIterator[str]:
    """Yield text chunks from the model as they arrive.

    No temperature is sent: current Claude models reject sampling parameters.
    LiteLLM maps reasoning_effort to Anthropic's output_config.effort, and
    drop_params skips it for models that do not support it.
    """
    settings = get_settings()
    response = await load_litellm().acompletion(
        model=settings.llm_model,
        messages=messages,
        stream=True,
        max_tokens=max_tokens,
        reasoning_effort=settings.llm_reasoning_effort,
        drop_params=True,
        **_traced(trace),
    )
    async for chunk in response:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


async def complete_json(
    messages: list[dict], schema: dict, *, name: str, max_tokens: int = 8000, trace: Trace | None = None
) -> dict:
    """One reply that matches a JSON schema (for the safety judge).

    Claude models get Anthropic's native structured output, asked for directly: LiteLLM 1.91.5
    only uses it for the Claude models it knows by name, and for newer ones falls back to a
    forced tool call, which current models reject. Other providers get the generic response_format.
    """
    settings = get_settings()
    response = await load_litellm().acompletion(
        model=settings.llm_model,
        messages=messages,
        max_tokens=max_tokens,
        reasoning_effort=settings.llm_reasoning_effort,
        drop_params=True,
        **structured_output(settings.llm_model, name, schema),
        **_traced(trace),
    )
    return parse_json(response.choices[0].message.content or "")


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict  # {} with "_invalid" set when the model's arguments weren't valid JSON


@dataclass
class AgentTurn:
    """One reply in a tool-using conversation."""

    text: str  # what the model said (may be empty)
    tool_calls: list[ToolCall] = field(default_factory=list)
    message: dict = field(default_factory=dict)  # the reply as-is, to add to the conversation


async def complete_with_tools(
    messages: list[dict], tools: list[dict], *, max_tokens: int = 4000, trace: Trace | None = None
) -> AgentTurn:
    """One turn of the agent: the model answers, calling any tools it chooses.

    Tools are OpenAI-style function definitions, which LiteLLM converts for each provider. The
    model decides whether to call one (current models reject forcing a particular tool).
    The reply is kept whole for the conversation, so anything the provider needs back next turn
    (like thinking blocks) is still there.
    """
    settings = get_settings()
    response = await load_litellm().acompletion(
        model=settings.llm_model,
        messages=messages,
        tools=tools,
        max_tokens=max_tokens,
        reasoning_effort=settings.llm_reasoning_effort,
        drop_params=True,
        **_traced(trace),
    )
    reply = response.choices[0].message
    calls = []
    for call in reply.tool_calls or []:
        try:
            arguments = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            arguments = {"_invalid": call.function.arguments}
        calls.append(ToolCall(id=call.id, name=call.function.name, arguments=arguments))
    message = reply.model_dump(exclude_none=True) if hasattr(reply, "model_dump") else dict(vars(reply))
    message["role"] = "assistant"
    return AgentTurn(text=(reply.content or "").strip(), tool_calls=calls, message=message)


def structured_output(model: str, name: str, schema: dict) -> dict:
    """The request setting that makes the reply match `schema`."""
    if model.startswith("anthropic/"):
        return {"output_format": {"type": "json_schema", "schema": schema}}
    return {"response_format": {"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}}}


def parse_json(text: str) -> dict:
    """Read a JSON reply, tolerating a ```json fence."""
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(cleaned)
