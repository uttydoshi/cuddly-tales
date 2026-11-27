"""Turns the model's token stream into whole words, and the finished text into a saved story."""

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import TypeVar

T = TypeVar("T")

WORDS_PER_MINUTE = 100  # a slow, read-aloud bedtime pace

_WORD_WITH_SPACE = re.compile(r"\S+\s+")


async def words_from_chunks(chunks: AsyncIterator[str]) -> AsyncIterator[str]:
    """Regroup arbitrary text chunks into whole words.

    Each yielded piece is one word plus the whitespace after it, so joining
    the pieces gives back exactly the original text.
    """
    buffer = ""
    async for chunk in chunks:
        buffer += chunk
        last_end = 0
        for match in _WORD_WITH_SPACE.finditer(buffer):
            yield match.group()
            last_end = match.end()
        buffer = buffer[last_end:]
    if buffer:
        yield buffer


def split_title(text: str) -> tuple[str | None, str]:
    """Split a leading "# Title" line from the story body."""
    first_line, _, rest = text.strip().partition("\n")
    if first_line.startswith("# "):
        return first_line[2:].strip() or None, rest.strip()
    return None, text.strip()


def count_words(text: str) -> int:
    return len(text.split())


def reading_minutes(word_count: int) -> int:
    return max(1, round(word_count / WORDS_PER_MINUTE))


async def with_keepalive(source: AsyncIterator[T], interval: float) -> AsyncIterator[T | None]:
    """Pass items through, yielding None whenever `interval` seconds pass with nothing new.

    The caller turns None into an SSE comment, so proxies such as CloudFront don't
    close a stream that goes quiet (the model thinking before it writes, or a long
    agent step). The pending read is never cancelled by a timeout, so no output is lost.
    """
    pending = asyncio.ensure_future(anext(source))
    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=interval)
            if not done:
                yield None
                continue
            try:
                item = pending.result()
            except StopAsyncIteration:
                return
            yield item
            pending = asyncio.ensure_future(anext(source))
    finally:
        if not pending.done():
            pending.cancel()


KEEPALIVE = ": keepalive\n\n"  # an SSE comment; EventSource ignores it


def sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event. Data is JSON so newlines in the text are safe."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
