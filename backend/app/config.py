"""App settings, read from environment variables (and a .env file at the repo root)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    llm_model: str
    database_url: str
    frontend_dist: Path


def get_settings() -> Settings:
    return Settings(
        llm_model=os.getenv("LLM_MODEL", "anthropic/claude-opus-5-5"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./cuddly_tales.db"),
        frontend_dist=Path(
            os.getenv("FRONTEND_DIST", REPO_ROOT / "frontend" / "dist" / "frontend" / "browser")
        ),
    )
