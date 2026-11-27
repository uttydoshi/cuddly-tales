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
    assert response.json() == {"id": 1, "name": "Arlo", "age": 5, "favourite_things": ["trains", "kites"]}
    assert client.get("/api/profile").json()["name"] == "Arlo"


@pytest.mark.parametrize("age", [1, 7])
def test_update_profile_rejects_age_outside_2_to_6(client, age):
    response = client.put("/api/profile", json={"name": "Arlo", "age": age, "favourite_things": []})
    assert response.status_code == 422


def test_update_profile_rejects_empty_name(client):
    response = client.put("/api/profile", json={"name": " ", "age": 3})
    assert response.status_code == 422
