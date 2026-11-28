"""Database tables."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import JSON, Column, DateTime, String
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


class AdventureStatus(StrEnum):
    in_progress = "in_progress"  # some nights are still to be written
    finished = "finished"  # every night has been written


class AgentRunStatus(StrEnum):
    pending = "pending"  # created; starts when the parent's page opens its stream
    running = "running"
    finished = "finished"  # did what it set out to do
    failed = "failed"  # stopped early: a limit, an error, or the goal not reached
    stopped = "stopped"  # the page was closed (or the connection lost) mid-run


class AgentRunKind(StrEnum):
    plan = "plan"  # plan a new adventure and write its first night
    next_night = "next_night"  # write the next night of an adventure in progress


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
    # A parent's heart: the story shows under Favourites.
    favourite: bool = False
    text: str | None = None
    word_count: int | None = None
    reading_minutes: int | None = None
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    read_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    # The safety and age check. None for stories written before the check existed.
    safety_status: SafetyStatus | None = None
    safety_report: dict | None = Field(default=None, sa_column=Column(JSON))

    # Set when the story is one night of an adventure the agent planned.
    adventure_id: int | None = Field(default=None, foreign_key="adventure.id", ondelete="CASCADE")
    night: int | None = None

    characters: list[Character] = Relationship(back_populates="stories", link_model=StoryCharacterLink)
    adventure: Optional["Adventure"] = Relationship()
    plot_cards: list["PlotCard"] = Relationship(
        back_populates="story",
        cascade_delete=True,
        sa_relationship_kwargs={"order_by": "PlotCard.position"},
    )


class PlotCard(SQLModel, table=True):
    """One beat of a story's plot, in order. The adventure agent writes these for every night."""

    id: int | None = Field(default=None, primary_key=True)
    story_id: int = Field(foreign_key="story.id", ondelete="CASCADE", index=True)
    position: int
    text: str

    story: Story = Relationship(back_populates="plot_cards")


class Adventure(SQLModel, table=True):
    """A story told over several nights. Each night is a Story with `adventure_id` and `night`."""

    id: int | None = Field(default=None, primary_key=True)
    title: str
    premise: str  # what the whole adventure is about, in a sentence or two
    nights: int
    bedtime: bool = False
    status: AdventureStatus = Field(default=AdventureStatus.in_progress, sa_type=String(20))
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class AgentRun(SQLModel, table=True):
    """One run of the adventure agent: its goal, what it was asked for, and how it ended."""

    id: int | None = Field(default=None, primary_key=True)
    kind: AgentRunKind = Field(sa_type=String(20))
    goal: str
    status: AgentRunStatus = Field(default=AgentRunStatus.pending, sa_type=String(20))
    trigger: str = Field(default="parent", sa_type=String(20))  # parent | schedule | run_now
    # What the parent asked for (plan runs).
    nights: int | None = None
    bedtime: bool = False
    theme: str | None = None
    character_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    adventure_id: int | None = Field(default=None, foreign_key="adventure.id", ondelete="SET NULL")
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    finished_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class AgentStep(SQLModel, table=True):
    """One thing the agent did, saved as it happens so the parent can watch (and look back)."""

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="agentrun.id", ondelete="CASCADE", index=True)
    position: int
    # A tool's name, or "message" for what the agent says between tools.
    tool: str = Field(sa_type=String(40))
    label: str  # what it's doing, for the parent: "Write night 1"
    result: str | None = None  # what came of it, for the parent: "412 words"
    ok: bool | None = None  # None while running
    detail: dict | None = Field(default=None, sa_column=Column(JSON))  # the tool's input and output
    started_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    finished_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
