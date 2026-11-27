"""Database tables."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, Column
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
    text: str | None = None
    word_count: int | None = None
    reading_minutes: int | None = None
    created_at: datetime = Field(default_factory=utc_now)
    read_at: datetime | None = None

    characters: list[Character] = Relationship(back_populates="stories", link_model=StoryCharacterLink)
