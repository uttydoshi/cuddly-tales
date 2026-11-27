"""Request and response shapes for the API."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.models import CharacterType, SafetyStatus, StoryStatus

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ChildProfileRead(BaseModel):
    id: int
    name: str
    age: int
    favourite_things: list[str]


class ChildProfileUpdate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    age: int = Field(ge=2, le=6)
    favourite_things: list[ShortText] = Field(default_factory=list, max_length=10)


class CharacterRead(BaseModel):
    id: int
    name: str
    type: CharacterType
    description: str
    traits: list[str]
    rules: list[str]
    image_url: str | None


class CharacterCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    type: CharacterType
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    traits: list[ShortText] = Field(default_factory=list, max_length=10)
    rules: list[ShortText] = Field(default_factory=list, max_length=10)

    @field_validator("type")
    @classmethod
    def not_latte_monster(cls, value: CharacterType) -> CharacterType:
        if value == CharacterType.latte_monster:
            raise ValueError("Latte monsters are created from a photo, not by hand")
        return value


class CharacterUpdate(CharacterCreate):
    """Every field is optional; only the fields sent are changed."""

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)] | None = None
    type: CharacterType | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)] | None = None
    traits: list[ShortText] | None = Field(default=None, max_length=10)
    rules: list[ShortText] | None = Field(default=None, max_length=10)


class CharacterRef(BaseModel):
    id: int
    name: str
    type: CharacterType


class StoryCreate(BaseModel):
    character_ids: list[int] = Field(min_length=1, max_length=6)
    bedtime: bool = False


class StorySummary(BaseModel):
    id: int
    title: str
    status: StoryStatus
    word_count: int | None
    reading_minutes: int | None
    created_at: datetime
    bedtime: bool
    characters: list[CharacterRef]
    # None for stories written before the safety check existed, or not written yet.
    safety_status: SafetyStatus | None


class StoryRead(StorySummary):
    text: str | None
    read_at: datetime | None
    # Every version the check looked at: scores, character rules and problems found.
    safety: dict | None


class StoryUpdate(BaseModel):
    """Parent edits. Only the fields sent are changed."""

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)] | None = None
    read: bool | None = None
    # A parent has read a story the safety check flagged, and says it's fine.
    approve: bool | None = None
