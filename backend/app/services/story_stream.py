"""Turns the model's token stream into whole words, and the finished text into a saved story."""

import json
import re
from collections.abc import AsyncIterator

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


def sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event. Data is JSON so newlines in the text are safe."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
