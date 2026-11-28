"""Langfuse tracing for every model call, through LiteLLM's Langfuse integration.

One trace per piece of work: writing a story (with its safety check and any rewrite), or one run
of the adventure agent (every turn, plus the chapter it writes and checks). Each model call is a
generation inside it, named for its step ("write", "safety-check", "agent-turn-3"), with the
prompt, the reply, tokens, cost and timing. Traces are tagged with the feature and where the app
runs ("live" or "local"); an adventure's runs share a session.

Off unless real Langfuse keys are set, so tests and a fresh checkout never send anything.
LANGFUSE_LOG_CONTENT=false keeps prompts and replies out of Langfuse (timings, tokens and cost only).
"""

import asyncio
import importlib.util
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field, replace

from app import config  # noqa: F401  (loads .env, and the keys from Secrets Manager on Lambda)

logger = logging.getLogger(__name__)

FLUSH_SECONDS = 10


def enabled() -> bool:
    """Real keys only: the placeholders from .env.example don't count."""
    public = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret = os.getenv("LANGFUSE_SECRET_KEY", "")
    return public.startswith("pk-lf-") and secret.startswith("sk-lf-") and "your" not in public + secret


def log_content() -> bool:
    return os.getenv("LANGFUSE_LOG_CONTENT", "true").strip().lower() not in {"false", "0", "no"}


def environment() -> str:
    return "live" if os.getenv("AWS_LAMBDA_FUNCTION_NAME") else "local"


@dataclass(frozen=True)
class Trace:
    """Where a model call belongs: the piece of work (trace) and the step within it."""

    feature: str  # "story" or "adventure-agent": the trace's name and first tag
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    session: str | None = None  # groups traces, e.g. every run of one adventure
    details: dict = field(default_factory=dict)  # story_id, run_id…
    step: str | None = None

    def at(self, step: str) -> "Trace":
        return replace(self, step=step)

    def in_session(self, session: str) -> "Trace":
        return replace(self, session=f"{environment()}-{session}")

    def metadata(self) -> dict:
        """What LiteLLM's Langfuse integration reads from a call's metadata."""
        data = {
            "trace_id": self.id,
            "trace_name": self.feature,
            "generation_name": self.step or self.feature,
            "tags": [self.feature, environment()],
            "trace_metadata": dict(self.details),
        }
        if self.session:
            data["session_id"] = self.session
        if not log_content():
            data["mask_input"] = True
            data["mask_output"] = True
        return data


# The LiteLLM module this tracing is written for (LiteLLM's Langfuse v4 integration).
INTEGRATION = "litellm.integrations.langfuse.langfuse_sdk"


def integration_available() -> bool:
    try:
        return importlib.util.find_spec(INTEGRATION) is not None
    except ModuleNotFoundError:
        return False


def setup(litellm) -> None:
    """Turn the integration on (once), when LiteLLM is first loaded. Tracing must never stop a
    story: with a LiteLLM that lacks the integration it stays off, with a warning."""
    if not enabled():
        return
    if not integration_available():
        logger.warning("Langfuse tracing is off: this LiteLLM has no %s", INTEGRATION)
        return
    for callbacks in (litellm.success_callback, litellm.failure_callback):
        if "langfuse" not in callbacks:
            callbacks.append("langfuse")


async def flush() -> None:
    """Send queued traces now. Called as each request ends: on Lambda the process is frozen
    once the response is done, so anything still queued would be lost."""
    if not enabled() or "litellm" not in sys.modules or not integration_available():
        return
    try:
        from litellm.integrations.langfuse.langfuse_sdk import flush_langfuse_tracing
        from litellm.litellm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER

        await asyncio.wait_for(GLOBAL_LOGGING_WORKER.flush(), FLUSH_SECONDS)  # LiteLLM's queue
        await asyncio.to_thread(flush_langfuse_tracing, FLUSH_SECONDS * 1000)  # the exporter's batches
    except Exception:
        logger.warning("Couldn't send traces to Langfuse", exc_info=True)
