from fastapi.testclient import TestClient

from app import aws_secrets
from app.db import normalize_url
from app.main import create_app


def test_normalize_url_uses_psycopg_for_postgres():
    neon = "postgresql://user:pw@ep-x-pooler.us-east-1.aws.neon.tech/db?sslmode=require"
    assert normalize_url(neon) == "postgresql+psycopg://user:pw@ep-x-pooler.us-east-1.aws.neon.tech/db?sslmode=require"
    assert normalize_url("postgres://u@h/db") == "postgresql+psycopg://u@h/db"
    assert normalize_url("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db"
    assert normalize_url("sqlite:///./x.db") == "sqlite:///./x.db"


def test_load_into_env_copies_secrets_but_keeps_values_already_set(monkeypatch):
    monkeypatch.setattr(aws_secrets, "read_secret", lambda secret_id: f"value-of-{secret_id}")
    monkeypatch.setenv("CLAUDE_API_KEY_SECRET", "cuddly-tales/claude-api-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL_SECRET", "cuddly-tales/database-url")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./already-set.db")

    aws_secrets.load_into_env()

    import os

    assert os.environ["ANTHROPIC_API_KEY"] == "value-of-cuddly-tales/claude-api-key"
    assert os.environ["DATABASE_URL"] == "sqlite:///./already-set.db"


def test_requests_without_the_cloudfront_secret_are_refused(engine, monkeypatch):
    monkeypatch.setattr(aws_secrets, "origin_secret", lambda: "s3cret")
    with TestClient(create_app(engine)) as client:
        assert client.get("/api/health").status_code == 403
        assert client.get("/api/health", headers={"x-origin-verify": "wrong"}).status_code == 403
        response = client.get("/api/health", headers={"x-origin-verify": "s3cret"})
        assert response.status_code == 200


def test_no_secret_locally_means_no_check(client):
    assert client.get("/api/health").status_code == 200
