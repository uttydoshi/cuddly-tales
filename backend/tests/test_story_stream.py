import asyncio

from app.services.story_stream import reading_minutes, split_title, with_keepalive, words_from_chunks


async def _collect(chunks):
    async def source():
        for chunk in chunks:
            yield chunk

    return [word async for word in words_from_chunks(source())]


def test_words_from_chunks_regroups_split_words():
    chunks = ["Mi", "nnie ch", "ased her", " ball", ".\nThe end"]
    words = asyncio.run(_collect(chunks))
    assert words == ["Minnie ", "chased ", "her ", "ball.\n", "The ", "end"]
    assert "".join(words) == "".join(chunks)


def test_split_title():
    assert split_title("# Sleepy Wolf\n\nOnce upon a time.") == ("Sleepy Wolf", "Once upon a time.")
    assert split_title("Once upon a time.") == (None, "Once upon a time.")


def test_reading_minutes_never_below_one():
    assert reading_minutes(10) == 1
    assert reading_minutes(450) == 4


def test_with_keepalive_fills_silences_without_losing_items():
    async def slow():
        yield "Once "
        await asyncio.sleep(0.25)
        yield "upon"

    async def collect():
        return [item async for item in with_keepalive(slow(), interval=0.1)]

    items = asyncio.run(collect())
    assert [i for i in items if i is not None] == ["Once ", "upon"]
    assert items.count(None) >= 1
    assert items[0] == "Once "
