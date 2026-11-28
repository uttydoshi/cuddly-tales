import pytest


def test_get_profile_returns_seeded_child(client):
    response = client.get("/api/profile")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Mira"
    assert body["age"] == 3
    assert "poodles" in body["favourite_things"]


def test_update_profile(client):
    payload = {"name": " Arlo ", "age": 5, "favourite_things": ["trains", "kites"]}
    response = client.put("/api/profile", json=payload)
    assert response.status_code == 200
    assert response.json() == {
        "id": 1, "name": "Arlo", "age": 5, "favourite_things": ["trains", "kites"], "stories_renamed": 0
    }
    assert client.get("/api/profile").json()["name"] == "Arlo"


@pytest.mark.parametrize("age", [1, 7])
def test_update_profile_rejects_age_outside_2_to_6(client, age):
    response = client.put("/api/profile", json={"name": "Arlo", "age": age, "favourite_things": []})
    assert response.status_code == 422


def test_update_profile_rejects_empty_name(client):
    response = client.put("/api/profile", json={"name": " ", "age": 3})
    assert response.status_code == 422


def test_new_name_replaces_the_old_one_in_stories_and_characters(client, engine):
    from sqlmodel import Session, select

    from app.models import Character, Story

    with Session(engine) as session:
        session.add(
            Story(
                title="Mira and the Kite",
                text="Mira laughed. \"MIRA!\" called Diggles. Mira's kite flew over Miranda's admiral hat.",
                safety_report={"attempts": [{"summary": "Mira flies a kite."}]},
            )
        )
        session.add(Story(title="A quiet night", text="The stars came out."))
        session.commit()

    response = client.put("/api/profile", json={"name": "Arlo", "age": 3, "favourite_things": []})
    assert response.json()["stories_renamed"] == 1

    with Session(engine) as session:
        story = session.exec(select(Story).where(Story.title == "Arlo and the Kite")).one()
        assert story.text == "Arlo laughed. \"ARLO!\" called Diggles. Arlo's kite flew over Miranda's admiral hat."
        assert story.safety_report["attempts"][0]["summary"] == "Arlo flies a kite."
        diggles = session.exec(select(Character).where(Character.name == "Diggles")).one()
        assert "fiercely loyal to Arlo" in diggles.traits
        assert not any("Mira" in r for r in diggles.rules)


def test_same_name_changes_no_stories(client):
    response = client.put("/api/profile", json={"name": "Mira", "age": 4, "favourite_things": []})
    assert response.json()["stories_renamed"] == 0
