import pytest

from app.services import llm

NEW_CHARACTER = {
    "name": "Captain Koala",
    "type": "custom",
    "description": "A sleepy koala who sails a teacup boat.",
    "traits": ["brave", "yawns a lot"],
    "rules": ["Falls asleep at least once."],
}


def test_list_characters_returns_seed_cast(client):
    response = client.get("/api/characters")
    assert response.status_code == 200
    characters = response.json()
    assert len(characters) == 10

    minnie = next(c for c in characters if c["name"] == "Minnie")
    assert minnie["type"] == "family"
    assert any("ball" in rule for rule in minnie["rules"])


def test_create_and_get_character(client):
    response = client.post("/api/characters", json=NEW_CHARACTER)
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "Captain Koala"
    assert created["rules"] == ["Falls asleep at least once."]

    fetched = client.get(f"/api/characters/{created['id']}").json()
    assert fetched == created
    assert len(client.get("/api/characters").json()) == 11


def test_create_trims_whitespace(client):
    response = client.post("/api/characters", json={**NEW_CHARACTER, "name": "  Captain Koala  "})
    assert response.json()["name"] == "Captain Koala"


@pytest.mark.parametrize(
    "change",
    [
        {"name": ""},
        {"name": "x" * 61},
        {"description": ""},
        {"type": "latte_monster"},
        {"type": "dragon"},
        {"rules": ["ok"] * 11},
        {"traits": [""]},
    ],
)
def test_create_rejects_invalid_input(client, change):
    assert client.post("/api/characters", json={**NEW_CHARACTER, **change}).status_code == 422


def test_get_unknown_character_is_404(client):
    assert client.get("/api/characters/9999").status_code == 404


def test_update_changes_only_sent_fields(client):
    created = client.post("/api/characters", json=NEW_CHARACTER).json()

    response = client.patch(f"/api/characters/{created['id']}", json={"rules": ["Snores like a kettle."]})
    assert response.status_code == 200
    updated = response.json()
    assert updated["rules"] == ["Snores like a kettle."]
    assert updated["name"] == "Captain Koala"
    assert client.get(f"/api/characters/{created['id']}").json()["rules"] == ["Snores like a kettle."]


def test_update_ignores_nulls(client):
    created = client.post("/api/characters", json=NEW_CHARACTER).json()
    response = client.patch(f"/api/characters/{created['id']}", json={"name": None})
    assert response.status_code == 200
    assert response.json()["name"] == "Captain Koala"


def test_update_unknown_character_is_404(client):
    assert client.patch("/api/characters/9999", json={"name": "Nobody"}).status_code == 404


def test_delete_character(client):
    created = client.post("/api/characters", json=NEW_CHARACTER).json()
    assert client.delete(f"/api/characters/{created['id']}").status_code == 204
    assert client.get(f"/api/characters/{created['id']}").status_code == 404
    assert client.delete(f"/api/characters/{created['id']}").status_code == 404


def test_delete_character_keeps_its_stories(client, monkeypatch):
    async def stream_text(messages, **kwargs):
        yield "# Koala Night\n\nCaptain Koala yawned."

    monkeypatch.setattr(llm, "stream_text", stream_text)
    by_name = {c["name"]: c["id"] for c in client.get("/api/characters").json()}
    story_id = client.post(
        "/api/stories", json={"character_ids": [by_name["Minnie"], by_name["Maverick"]]}
    ).json()["id"]
    client.get(f"/api/stories/{story_id}/stream")

    assert client.delete(f"/api/characters/{by_name['Minnie']}").status_code == 204

    story = client.get(f"/api/stories/{story_id}").json()
    assert story["text"] == "Captain Koala yawned."
    assert [c["name"] for c in story["characters"]] == ["Maverick"]
