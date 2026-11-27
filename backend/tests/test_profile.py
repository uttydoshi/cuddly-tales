def test_get_profile_returns_seeded_child(client):
    response = client.get("/api/profile")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Mira"
    assert body["age"] == 3
    assert "poodles" in body["favourite_things"]
