"""FastAPI entry point. Run with: uvicorn app.main:app --reload (from backend/)."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.config import get_settings
from app.db import create_tables, make_engine
from app.routers import characters, profile, stories
from app.seed import seed_if_empty


def create_app(engine: Engine | None = None, frontend_dist: Path | None = None) -> FastAPI:
    settings = get_settings()
    engine = engine or make_engine(settings.database_url)
    frontend_dist = (frontend_dist or settings.frontend_dist).resolve()

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

    app.include_router(profile.router)
    app.include_router(characters.router)
    app.include_router(stories.router)

    # The built Angular app. Registered last so /api routes win.
    # Real files are served as-is; any other path gets index.html so
    # Angular's router can handle deep links like /stories/3.
    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Not found")
        index = frontend_dist / "index.html"
        if not index.is_file():
            raise HTTPException(404, "Frontend not built. Run `npm run build` in frontend/.")
        candidate = (frontend_dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(frontend_dist):
            return FileResponse(candidate)
        return FileResponse(index)

    return app


app = create_app()
