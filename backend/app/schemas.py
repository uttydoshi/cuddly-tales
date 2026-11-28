"""Request and response shapes for the API."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, StringConstraints, field_validator

from app.models import (
    AdventureStatus,
    AgentRunKind,
    AgentRunStatus,
    CharacterType,
    SafetyStatus,
    StoryStatus,
)

def as_utc(value: datetime) -> datetime:
    """SQLite gives back times without a zone; they were saved as UTC, so say so."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# Sent with "+00:00", so browsers don't read the time as local.
UtcDatetime = Annotated[datetime, AfterValidator(as_utc)]

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ChildProfileRead(BaseModel):
    id: int
    name: str
    age: int
    favourite_things: list[str]


class ChildProfileSaved(ChildProfileRead):
    # How many stories had the child's old name changed to the new one.
    stories_renamed: int = 0


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


class AdventureRef(BaseModel):
    """Which adventure a story is one night of."""

    id: int
    title: str
    night: int
    nights: int


class StorySummary(BaseModel):
    id: int
    title: str
    status: StoryStatus
    word_count: int | None
    reading_minutes: int | None
    created_at: datetime
    bedtime: bool
    favourite: bool
    characters: list[CharacterRef]
    # None for stories written before the safety check existed, or not written yet.
    safety_status: SafetyStatus | None
    adventure: AdventureRef | None = None


class StoryRead(StorySummary):
    text: str | None
    read_at: datetime | None
    # Every version the check looked at: scores, character rules and problems found.
    safety: dict | None
    # The plot, beat by beat, for stories planned by the adventure agent.
    plot_cards: list[str] = []


class StoryUpdate(BaseModel):
    """Parent edits. Only the fields sent are changed."""

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)] | None = None
    read: bool | None = None
    # A parent has read a story the safety check flagged, and says it's fine.
    approve: bool | None = None
    favourite: bool | None = None


class AdventureCreate(BaseModel):
    """A parent asks the agent to plan an adventure."""

    nights: int = Field(default=5, ge=2, le=7)
    bedtime: bool = False
    # Characters the parent wants in it; the agent chooses the rest.
    character_ids: list[int] = Field(default_factory=list, max_length=6)
    theme: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None


class NextNight(BaseModel):
    trigger: Literal["parent", "run_now"] = "parent"


class NightRead(BaseModel):
    night: int
    story_id: int
    title: str
    status: StoryStatus
    safety_status: SafetyStatus | None
    plot_cards: list[str]


class AdventureRead(BaseModel):
    id: int
    title: str
    premise: str
    nights: int
    bedtime: bool
    status: AdventureStatus
    created_at: UtcDatetime
    chapters: list[NightRead]


class AgentStepRead(BaseModel):
    id: int
    position: int
    tool: str
    label: str
    result: str | None
    ok: bool | None
    detail: dict | None
    started_at: UtcDatetime
    finished_at: UtcDatetime | None


class AgentRunRead(BaseModel):
    id: int
    kind: AgentRunKind
    goal: str
    status: AgentRunStatus
    trigger: str
    error: str | None
    created_at: UtcDatetime
    finished_at: UtcDatetime | None
    adventure: AdventureRead | None
    steps: list[AgentStepRead]
