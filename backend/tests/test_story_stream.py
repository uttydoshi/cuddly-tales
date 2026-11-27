import asyncio

from app.services.story_stream import reading_minutes, split_title, words_from_chunks


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
