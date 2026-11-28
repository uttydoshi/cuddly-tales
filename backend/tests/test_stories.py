import json
from datetime import timedelta

import pytest
from sqlmodel import Session

from app.models import Story, StoryStatus, utc_now
from app.services import llm, safety

STORY_CHUNKS = ["# The Ball ", "Hunt\n\nMin", "nie chased", " her ball.\n\n", "Every", "one yawned."]


def fake_stream(chunks):
    async def stream_text(messages, **kwargs):
        for chunk in chunks:
            yield chunk

    return stream_text


def failing_stream():
    async def stream_text(messages, **kwargs):
        yield "Once "
        raise RuntimeError("provider down")

    return stream_text


def parse_events(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


@pytest.fixture(autouse=True)
def check_passes(monkeypatch):
    """These tests are about writing and saving; the safety check has its own tests."""

    async def check_story(title, body, child, characters, *, bedtime, earlier=()):
        return safety.Attempt(passed=True, word_count=len(body.split()), scariness=1)

    monkeypatch.setattr(safety, "check_story", check_story)


@pytest.fixture
def character_ids(client):
    by_name = {c["name"]: c["id"] for c in client.get("/api/characters").json()}
    return [by_name["Minnie"], by_name["Maverick"]]


def test_create_story_is_planned_with_characters(client, character_ids):
    response = client.post("/api/stories", json={"character_ids": character_ids})
    assert response.status_code == 201
    story = response.json()
    assert story["status"] == "planned"
    assert story["title"] == "A story with Minnie and Maverick"
    assert [c["name"] for c in story["characters"]] == ["Minnie", "Maverick"]
    assert story["text"] is None


def test_story_characters_carry_their_type(client, character_ids):
    """The type picks a character's placeholder badge on story cards."""
    client.post("/api/stories", json={"character_ids": character_ids})
    story = client.get("/api/stories").json()[0]
    assert [c["type"] for c in story["characters"]] == ["family", "family"]


def test_create_story_rejects_unknown_character(client):
    response = client.post("/api/stories", json={"character_ids": [9999]})
    assert response.status_code == 404


def test_create_story_needs_at_least_one_character(client):
    response = client.post("/api/stories", json={"character_ids": []})
    assert response.status_code == 422


def test_stream_sends_whole_words_then_saves(client, engine, character_ids, monkeypatch):
    monkeypatch.setattr(llm, "stream_text", fake_stream(STORY_CHUNKS))
    story_id = client.post("/api/stories", json={"character_ids": character_ids}).json()["id"]

    response = client.get(f"/api/stories/{story_id}/stream")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = parse_events(response.text)
    words = [data["text"] for name, data in events if name == "word"]
    assert words == ["# ", "The ", "Ball ", "Hunt\n\n", "Minnie ", "chased ", "her ", "ball.\n\n", "Everyone ", "yawned."]
    assert events[-1] == ("done", {"id": story_id, "title": "The Ball Hunt", "safety": "passed"})

    with Session(engine) as session:
        story = session.get(Story, story_id)
        assert story.status == StoryStatus.written
        assert story.title == "The Ball Hunt"
        assert story.text == "Minnie chased her ball.\n\nEveryone yawned."
        assert story.word_count == 6
        assert story.reading_minutes == 1


def test_stream_twice_is_rejected(client, character_ids, monkeypatch):
    monkeypatch.setattr(llm, "stream_text", fake_stream(STORY_CHUNKS))
    story_id = client.post("/api/stories", json={"character_ids": character_ids}).json()["id"]
    client.get(f"/api/stories/{story_id}/stream")
    assert client.get(f"/api/stories/{story_id}/stream").status_code == 409


def test_stream_failure_sends_error_and_keeps_story_planned(client, engine, character_ids, monkeypatch):
    monkeypatch.setattr(llm, "stream_text", failing_stream())
    story_id = client.post("/api/stories", json={"character_ids": character_ids}).json()["id"]

    events = parse_events(client.get(f"/api/stories/{story_id}/stream").text)
    assert events[-1][0] == "error"

    with Session(engine) as session:
        story = session.get(Story, story_id)
        assert story.status == StoryStatus.planned
        assert story.text is None


def test_stream_unknown_story_is_404(client):
    assert client.get("/api/stories/9999/stream").status_code == 404


def test_list_stories_newest_first(client, character_ids, monkeypatch):
    monkeypatch.setattr(llm, "stream_text", fake_stream(STORY_CHUNKS))
    first = client.post("/api/stories", json={"character_ids": character_ids[:1]}).json()["id"]
    second = client.post("/api/stories", json={"character_ids": character_ids}).json()["id"]
    client.get(f"/api/stories/{second}/stream")

    stories = client.get("/api/stories").json()
    assert [s["id"] for s in stories] == [second, first]
    assert stories[0]["title"] == "The Ball Hunt"
    assert stories[0]["status"] == "written"
    assert "text" not in stories[0]


def test_get_story_returns_text(client, character_ids, monkeypatch):
    monkeypatch.setattr(llm, "stream_text", fake_stream(STORY_CHUNKS))
    story_id = client.post("/api/stories", json={"character_ids": character_ids}).json()["id"]
    client.get(f"/api/stories/{story_id}/stream")

    story = client.get(f"/api/stories/{story_id}").json()
    assert story["text"].startswith("Minnie chased her ball.")
    assert story["reading_minutes"] == 1


def test_get_unknown_story_is_404(client):
    assert client.get("/api/stories/9999").status_code == 404


def written_story(client, character_ids, monkeypatch) -> int:
    monkeypatch.setattr(llm, "stream_text", fake_stream(STORY_CHUNKS))
    story_id = client.post("/api/stories", json={"character_ids": character_ids}).json()["id"]
    client.get(f"/api/stories/{story_id}/stream")
    return story_id


def test_edit_title_and_text_recounts_words(client, character_ids, monkeypatch):
    story_id = written_story(client, character_ids, monkeypatch)
    response = client.patch(
        f"/api/stories/{story_id}",
        json={"title": "  Minnie's Big Night ", "text": "Minnie slept. " * 150},
    )
    assert response.status_code == 200
    story = response.json()
    assert story["title"] == "Minnie's Big Night"
    assert story["word_count"] == 300
    assert story["reading_minutes"] == 3
    assert client.get(f"/api/stories/{story_id}").json()["word_count"] == 300


def test_mark_read_and_unread(client, character_ids, monkeypatch):
    story_id = written_story(client, character_ids, monkeypatch)

    story = client.patch(f"/api/stories/{story_id}", json={"read": True}).json()
    assert story["status"] == "read"
    assert story["read_at"] is not None

    story = client.patch(f"/api/stories/{story_id}", json={"read": False}).json()
    assert story["status"] == "written"
    assert story["read_at"] is None


def test_favourite_and_unfavourite(client, character_ids, monkeypatch):
    story_id = written_story(client, character_ids, monkeypatch)
    assert client.get(f"/api/stories/{story_id}").json()["favourite"] is False

    story = client.patch(f"/api/stories/{story_id}", json={"favourite": True}).json()
    assert story["favourite"] is True
    assert story["status"] == "written"  # a heart doesn't mark it read
    assert client.get("/api/stories").json()[0]["favourite"] is True

    assert client.patch(f"/api/stories/{story_id}", json={"favourite": False}).json()["favourite"] is False


def test_cannot_edit_text_or_read_a_planned_story(client, character_ids):
    story_id = client.post("/api/stories", json={"character_ids": character_ids}).json()["id"]
    assert client.patch(f"/api/stories/{story_id}", json={"text": "Hi."}).status_code == 409
    assert client.patch(f"/api/stories/{story_id}", json={"read": True}).status_code == 409
    assert client.patch(f"/api/stories/{story_id}", json={"title": "Soon"}).status_code == 200


def test_edit_rejects_empty_title(client, character_ids, monkeypatch):
    story_id = written_story(client, character_ids, monkeypatch)
    assert client.patch(f"/api/stories/{story_id}", json={"title": "  "}).status_code == 422


def test_edit_unknown_story_is_404(client):
    assert client.patch("/api/stories/9999", json={"title": "x"}).status_code == 404


def test_delete_story_keeps_its_characters(client, character_ids, monkeypatch):
    story_id = written_story(client, character_ids, monkeypatch)
    assert client.delete(f"/api/stories/{story_id}").status_code == 204
    assert client.get(f"/api/stories/{story_id}").status_code == 404
    assert client.get("/api/stories").json() == []
    assert len(client.get("/api/characters").json()) == 10
    assert client.delete(f"/api/stories/{story_id}").status_code == 404


def test_daily_limit_stops_new_stories(client, character_ids, monkeypatch):
    monkeypatch.setenv("MAX_STORIES_PER_DAY", "2")
    for _ in range(2):
        assert client.post("/api/stories", json={"character_ids": character_ids}).status_code == 201

    response = client.post("/api/stories", json={"character_ids": character_ids})
    assert response.status_code == 429
    assert "Come back tomorrow" in response.json()["detail"]


def test_daily_limit_counts_only_the_last_24_hours(client, engine, character_ids, monkeypatch):
    monkeypatch.setenv("MAX_STORIES_PER_DAY", "1")
    story_id = client.post("/api/stories", json={"character_ids": character_ids}).json()["id"]
    with Session(engine) as session:
        story = session.get(Story, story_id)
        story.created_at = utc_now() - timedelta(hours=25)
        session.add(story)
        session.commit()

    assert client.post("/api/stories", json={"character_ids": character_ids}).status_code == 201


def test_daily_limit_of_zero_means_no_limit(client, character_ids, monkeypatch):
    monkeypatch.setenv("MAX_STORIES_PER_DAY", "0")
    for _ in range(3):
        assert client.post("/api/stories", json={"character_ids": character_ids}).status_code == 201


def test_story_is_for_any_time_unless_bedtime_is_asked_for(client, character_ids):
    anytime = client.post("/api/stories", json={"character_ids": character_ids}).json()
    bedtime = client.post("/api/stories", json={"character_ids": character_ids, "bedtime": True}).json()
    assert anytime["bedtime"] is False
    assert bedtime["bedtime"] is True
    assert client.get(f"/api/stories/{bedtime['id']}").json()["bedtime"] is True
    assert {s["id"]: s["bedtime"] for s in client.get("/api/stories").json()} == {anytime["id"]: False, bedtime["id"]: True}


def test_bedtime_flag_reaches_the_prompt(client, character_ids, monkeypatch):
    seen = {}

    async def stream_text(messages, **kwargs):
        seen["user"] = messages[1]["content"]
        yield "# Sleepy\n\nGoodnight."

    monkeypatch.setattr(llm, "stream_text", stream_text)
    story_id = client.post("/api/stories", json={"character_ids": character_ids, "bedtime": True}).json()["id"]
    client.get(f"/api/stories/{story_id}/stream")
    assert "bedtime story" in seen["user"]


def test_new_story_prompt_lists_earlier_stories_and_a_kind_of_plot(client, character_ids, monkeypatch):
    prompts = []

    def recording(chunks):
        async def stream_text(messages, **kwargs):
            prompts.append(messages)
            for chunk in chunks:
                yield chunk

        return stream_text

    monkeypatch.setattr(llm, "stream_text", recording(STORY_CHUNKS))
    first = client.post("/api/stories", json={"character_ids": character_ids}).json()["id"]
    client.get(f"/api/stories/{first}/stream")
    second = client.post("/api/stories", json={"character_ids": character_ids}).json()["id"]
    client.get(f"/api/stories/{second}/stream")

    assert "already told" not in prompts[0][1]["content"]  # nothing written before the first
    # The first story is listed with what happens in it (its opening, as the fake check gave no summary).
    assert "- The Ball Hunt: Minnie chased her ball." in prompts[1][1]["content"]
    assert "The kind of story:" in prompts[1][1]["content"]
