"""Request and response shapes for the API."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models import CharacterType, StoryStatus


class ChildProfileRead(BaseModel):
    id: int
    name: str
    age: int
    favourite_things: list[str]


class CharacterRead(BaseModel):
    id: int
    name: str
    type: CharacterType
    description: str
    traits: list[str]
    rules: list[str]
    image_url: str | None


class CharacterRef(BaseModel):
    id: int
    name: str


class StoryCreate(BaseModel):
    character_ids: list[int] = Field(min_length=1, max_length=6)


class StorySummary(BaseModel):
    id: int
    title: str
    status: StoryStatus
    word_count: int | None
    reading_minutes: int | None
    created_at: datetime
    characters: list[CharacterRef]


class StoryRead(StorySummary):
    text: str | None
    read_at: datetime | None
