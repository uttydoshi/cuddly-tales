import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def app_client(engine, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<app-root></app-root>")
    (dist / "main-abc.js").write_text("console.log('app')")
    (tmp_path / "secret.txt").write_text("do not serve")
    with TestClient(create_app(engine, frontend_dist=dist)) as client:
        yield client


def test_serves_built_files(app_client):
    response = app_client.get("/main-abc.js")
    assert response.status_code == 200
    assert "console.log" in response.text


def test_deep_links_get_index_html(app_client):
    for path in ["/", "/stories", "/stories/3"]:
        response = app_client.get(path)
        assert response.status_code == 200
        assert "<app-root>" in response.text


def test_unknown_api_path_is_404_not_index(app_client):
    assert app_client.get("/api/nope").status_code == 404


def test_cannot_read_outside_dist(app_client):
    response = app_client.get("/%2E%2E/secret.txt")
    assert "do not serve" not in response.text


def test_api_still_works(app_client):
    assert app_client.get("/api/health").json() == {"status": "ok"}
