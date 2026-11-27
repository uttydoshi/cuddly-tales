"""App settings, read from environment variables (and a .env file at the repo root)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from app import aws_secrets

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
aws_secrets.load_into_env()  # on Lambda: the Claude key and database URL; locally a no-op


@dataclass(frozen=True)
class Settings:
    llm_model: str
    llm_reasoning_effort: str | None
    max_stories_per_day: int | None
    database_url: str
    frontend_dist: Path


def get_settings() -> Settings:
    return Settings(
        llm_model=os.getenv("LLM_MODEL", "anthropic/claude-opus-5-5"),
        # How long the model thinks before writing. "low" gets the first word on screen
        # quickly; a bedtime story does not need deep reasoning. Empty = provider default.
        llm_reasoning_effort=os.getenv("LLM_REASONING_EFFORT", "low") or None,
        # The site has no sign-in, so this caps what anyone can spend on the LLM.
        # Counts stories started in the last 24 hours. 0 or empty = no limit.
        max_stories_per_day=int(os.getenv("MAX_STORIES_PER_DAY", "30") or 0) or None,
        database_url=os.getenv("DATABASE_URL", "sqlite:///./cuddly_tales.db"),
        frontend_dist=Path(
            os.getenv("FRONTEND_DIST", REPO_ROOT / "frontend" / "dist" / "frontend" / "browser")
        ),
    )
