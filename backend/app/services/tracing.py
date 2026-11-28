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
import base64
import importlib.util
import logging
import os
import sys
import uuid
from contextvars import ContextVar
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
        root = root_span(self)
        if root is not None:
            data["litellm_parent_otel_span"] = root
        return data


# --- The root span: one per story or agent run ---
# Langfuse builds its trace list (and its tag and environment filters) from each trace's root
# observation. LiteLLM only sends the model calls, so each trace gets a root span of its own,
# sent by this module: it carries the trace's name, tags, environment, session and details, and
# the model calls hang under it. It starts with the first model call and ends with flush(trace).

_roots: dict[str, object] = {}  # open root spans, by trace id
_provider = None  # this module's OpenTelemetry provider, made on first use
_next_trace_id: ContextVar[int | None] = ContextVar("_next_trace_id", default=None)
MAX_OPEN_ROOTS = 200  # a run cut off mid-way never ends its root; don't let those pile up


def _root_provider():
    """An OpenTelemetry provider that sends to the same Langfuse project as LiteLLM. Its trace
    ids are ours, so the root and LiteLLM's spans are one trace."""
    global _provider
    if _provider is None:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.id_generator import RandomIdGenerator

        class OurTraceIds(RandomIdGenerator):
            def generate_trace_id(self) -> int:
                return _next_trace_id.get() or super().generate_trace_id()

        host = os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com").rstrip("/")
        keys = f"{os.environ['LANGFUSE_PUBLIC_KEY']}:{os.environ['LANGFUSE_SECRET_KEY']}"
        exporter = OTLPSpanExporter(
            endpoint=f"{host}/api/public/otel/v1/traces",
            headers={"Authorization": "Basic " + base64.b64encode(keys.encode()).decode()},
        )
        provider = TracerProvider(
            resource=Resource.create({"service.name": "cuddly-tales", "deployment.environment": environment()}),
            id_generator=OurTraceIds(),
            shutdown_on_exit=False,  # flush() sends everything; nothing is left for exit
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        _provider = provider
    return _provider


def root_span(trace: "Trace"):
    """The trace's root span, started on first use. None when tracing is off."""
    if not enabled() or not integration_available():
        return None
    root = _roots.get(trace.id)
    if root is None:
        if len(_roots) >= MAX_OPEN_ROOTS:
            _roots.pop(next(iter(_roots))).end()
        attributes = {
            "langfuse.trace.name": trace.feature,
            "langfuse.trace.tags": [trace.feature, environment()],
            "langfuse.environment": environment(),
            **{f"langfuse.trace.metadata.{key}": str(value) for key, value in trace.details.items()},
        }
        token = _next_trace_id.set(int(trace.id, 16))
        try:
            root = _root_provider().get_tracer("cuddly-tales").start_span(trace.feature, attributes=attributes)
        finally:
            _next_trace_id.reset(token)
        _roots[trace.id] = root
    if trace.session:
        root.set_attribute("session.id", trace.session)
        root.set_attribute("langfuse.session.id", trace.session)
    return root


def _end_root(trace: "Trace | None") -> None:
    if trace is None:
        return
    root = _roots.pop(trace.id, None)
    if root is not None:
        if trace.session:
            root.set_attribute("session.id", trace.session)
            root.set_attribute("langfuse.session.id", trace.session)
        root.end()


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
    # Langfuse's environment field ("live" or "local"), which its views filter by. Without this,
    # LiteLLM labels every trace "production", wherever it ran. LiteLLM reads the first for model
    # calls and the second for the span around each call.
    for name in ("LANGFUSE_TRACING_ENVIRONMENT", "OTEL_ENVIRONMENT_NAME"):
        os.environ.setdefault(name, environment())
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

    providers = {id(_provider): _provider} if _provider is not None else {}
    for logger_ in _in_memory_loggers:
        for provider in [getattr(logger_, "_tracer_provider", None), *(getattr(logger_, "_tracer_provider_cache", None) or {}).values()]:
            if provider is not None and hasattr(provider, "force_flush"):
                providers[id(provider)] = provider
    return list(providers.values())


async def flush(trace: "Trace | None" = None) -> None:
    """End the trace's root span and send queued traces now. Called as each request ends: on
    Lambda the process is frozen once the response is done, so anything still queued would be lost.

    After a model call returns, LiteLLM hands its logging to a background queue; the spans are
    only made when that queue runs, and then wait in a batch. So: wait for the hand-off, run the
    queue, then flush the batch."""
    if not enabled() or "litellm" not in sys.modules or not integration_available():
        return
    try:
        _end_root(trace)
        from litellm.litellm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER

        handoffs = _litellm_logging_tasks()
        if handoffs:
            await asyncio.wait(handoffs, timeout=FLUSH_SECONDS)
        await asyncio.wait_for(GLOBAL_LOGGING_WORKER.flush(), FLUSH_SECONDS)  # the spans get made
        for provider in _span_providers():  # and sent to Langfuse
            await asyncio.to_thread(provider.force_flush, FLUSH_SECONDS * 1000)
    except Exception:
        logger.warning("Couldn't send traces to Langfuse", exc_info=True)
