"""Database tables."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class CharacterType(StrEnum):
    family = "family"
    original = "original"
    folklore = "folklore"
    latte_monster = "latte_monster"
    custom = "custom"


class StoryStatus(StrEnum):
    idea = "idea"
    planned = "planned"
    written = "written"
    read = "read"


class SafetyStatus(StrEnum):
    passed = "passed"  # passed the safety and age check first time
    rewritten = "rewritten"  # failed, was rewritten once, and the rewrite passed
    needs_review = "needs_review"  # still failed (or couldn't be checked): a parent should read it first
    approved = "approved"  # a parent read a flagged story and said it's fine


class ChildProfile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    age: int = Field(ge=2, le=6)
    favourite_things: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class StoryCharacterLink(SQLModel, table=True):
    story_id: int = Field(foreign_key="story.id", primary_key=True, ondelete="CASCADE")
    character_id: int = Field(foreign_key="character.id", primary_key=True, ondelete="CASCADE")


class Character(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    type: CharacterType
    description: str
    traits: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    rules: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    image_url: str | None = None

    stories: list["Story"] = Relationship(back_populates="characters", link_model=StoryCharacterLink)


class Story(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    status: StoryStatus = StoryStatus.planned
    # A bedtime story ends calm and sleepy and opens in night mode; otherwise it's for any time.
    bedtime: bool = False
    text: str | None = None
    word_count: int | None = None
    reading_minutes: int | None = None
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    read_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    # The safety and age check. None for stories written before the check existed.
    safety_status: SafetyStatus | None = None
    safety_report: dict | None = Field(default=None, sa_column=Column(JSON))

    characters: list[Character] = Relationship(back_populates="stories", link_model=StoryCharacterLink)
