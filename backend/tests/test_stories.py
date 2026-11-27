import json

import pytest
from sqlmodel import Session

from app.models import Story, StoryStatus
from app.services import llm

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
    assert events[-1] == ("done", {"id": story_id, "title": "The Ball Hunt"})

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
