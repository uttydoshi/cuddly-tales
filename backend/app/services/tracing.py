"""Langfuse tracing for every model call, through LiteLLM's OpenTelemetry integration for Langfuse
(`langfuse_otel`): model calls become OpenTelemetry spans, sent to Langfuse's OpenTelemetry endpoint.

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
        parent = _parent_span(self.id)
        if parent is not None:
            data["litellm_parent_otel_span"] = parent
        return data


def _parent_span(trace_id: str):
    """An OpenTelemetry parent for every call in one trace. Langfuse groups spans by their
    OpenTelemetry trace, so without one each model call would be a trace of its own. Our trace id
    is already 32 hex characters, a valid OpenTelemetry trace id."""
    if not enabled():
        return None
    try:
        from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
    except ImportError:
        return None
    context = SpanContext(
        trace_id=int(trace_id, 16),
        span_id=int(trace_id[:16], 16) or 1,
        is_remote=True,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    return NonRecordingSpan(context)


# What this tracing needs: LiteLLM's OpenTelemetry integration for Langfuse, and the
# OpenTelemetry SDK and exporter it sends with (in requirements.txt).
CALLBACK = "langfuse_otel"
NEEDED = (
    "litellm.integrations.langfuse.langfuse_otel",
    "opentelemetry.sdk.trace",
    "opentelemetry.exporter.otlp.proto.http.trace_exporter",
    "pydantic_settings",  # imported by LiteLLM's OpenTelemetry logger, though LiteLLM doesn't declare it
)


def integration_available() -> bool:
    try:
        return all(importlib.util.find_spec(module) is not None for module in NEEDED)
    except ModuleNotFoundError:
        return False


def setup(litellm) -> None:
    """Turn the integration on (once), when LiteLLM is first loaded. Tracing must never stop a
    story: if anything it needs is missing, it stays off, with a warning."""
    if not enabled():
        return
    if not integration_available():
        logger.warning("Langfuse tracing is off: missing one of %s", ", ".join(NEEDED))
        return
    if CALLBACK not in litellm.callbacks:
        litellm.callbacks.append(CALLBACK)


def _litellm_logging_tasks() -> list[asyncio.Task]:
    """LiteLLM's hand-offs to its logging queue, still pending after a model call returns."""
    current = asyncio.current_task()
    tasks = []
    for task in asyncio.all_tasks():
        code = getattr(task.get_coro(), "cr_code", None)
        if task is not current and code and "litellm" in code.co_filename and "logging" in code.co_name:
            tasks.append(task)
    return tasks


def _span_providers() -> list:
    """The OpenTelemetry providers LiteLLM sends spans through. For Langfuse it makes one per set of
    credentials (kept in each logger's cache), not the global provider."""
    from litellm.litellm_core_utils.litellm_logging import _in_memory_loggers

    providers = {}
    for logger_ in _in_memory_loggers:
        for provider in [getattr(logger_, "_tracer_provider", None), *(getattr(logger_, "_tracer_provider_cache", None) or {}).values()]:
            if provider is not None and hasattr(provider, "force_flush"):
                providers[id(provider)] = provider
    return list(providers.values())


async def flush() -> None:
    """Send queued traces now. Called as each request ends: on Lambda the process is frozen
    once the response is done, so anything still queued would be lost.

    After a model call returns, LiteLLM hands its logging to a background queue; the spans are
    only made when that queue runs, and then wait in a batch. So: wait for the hand-off, run the
    queue, then flush the batch."""
    if not enabled() or "litellm" not in sys.modules or not integration_available():
        return
    try:
        from litellm.litellm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER

        handoffs = _litellm_logging_tasks()
        if handoffs:
            await asyncio.wait(handoffs, timeout=FLUSH_SECONDS)
        await asyncio.wait_for(GLOBAL_LOGGING_WORKER.flush(), FLUSH_SECONDS)  # the spans get made
        for provider in _span_providers():  # and sent to Langfuse
            await asyncio.to_thread(provider.force_flush, FLUSH_SECONDS * 1000)
    except Exception:
        logger.warning("Couldn't send traces to Langfuse", exc_info=True)
