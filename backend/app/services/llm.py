"""The only place that talks to LiteLLM. Swap this out (or monkeypatch it) in tests."""

import os
from collections.abc import AsyncIterator
from types import ModuleType

from app.config import get_settings


def load_litellm() -> ModuleType:
    """Import LiteLLM on first use, not at app start.

    LiteLLM takes seconds to import, and Lambda allows 10 seconds for the app to
    start. Loading it here keeps start-up fast; only the first story pays for it.
    Its built-in price list is used, so it doesn't download one from GitHub.
    """
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    import litellm

    return litellm


async def stream_text(messages: list[dict], *, max_tokens: int = 4000) -> AsyncIterator[str]:
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
    )
    async for chunk in response:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
