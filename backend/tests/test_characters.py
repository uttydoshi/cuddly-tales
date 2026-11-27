def test_list_characters_returns_seed_cast(client):
    response = client.get("/api/characters")
    assert response.status_code == 200
    characters = response.json()
    assert len(characters) == 10

    minnie = next(c for c in characters if c["name"] == "Minnie")
    assert minnie["type"] == "family"
    assert any("ball" in rule for rule in minnie["rules"])
