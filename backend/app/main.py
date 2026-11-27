"""FastAPI entry point. Run with: uvicorn app.main:app --reload (from backend/)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.config import get_settings
from app.db import create_tables, make_engine
from app.seed import seed_if_empty


def create_app(engine: Engine | None = None) -> FastAPI:
    settings = get_settings()
    engine = engine or make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        create_tables(engine)
        with Session(engine) as session:
            seed_if_empty(session)
        yield

    app = FastAPI(title="Cuddly Tales", lifespan=lifespan)
    app.state.engine = engine

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
