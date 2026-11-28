import logging
import random
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlmodel import Session, func, select

from app.config import get_settings
from app.db import get_session
from app.models import Adventure, AgentRun, Character, ChildProfile, SafetyStatus, Story, StoryStatus, utc_now
from app.schemas import AdventureRef, CharacterRef, StoryCreate, StoryRead, StorySummary, StoryUpdate
from app.services import llm, safety, tracing
from app.services.story_prompt import EARLIER_STORIES, PLOTS, build_story_messages
from app.services.story_stream import (
    KEEPALIVE,
    await_with_keepalive,
    count_words,
    reading_minutes,
    split_title,
    sse,
    with_keepalive,
    words_from_chunks,
)

logger = logging.getLogger(__name__)

KEEPALIVE_SECONDS = 15  # well inside CloudFront's 60-second wait between bytes

router = APIRouter(prefix="/api/stories", tags=["stories"])


def to_story_read(story: Story) -> StoryRead:
    return StoryRead(
        id=story.id,
        title=story.title,
        status=story.status,
        word_count=story.word_count,
        reading_minutes=story.reading_minutes,
        created_at=story.created_at,
        bedtime=story.bedtime,
        favourite=story.favourite,
        verified_at=story.verified_at,
        safety_status=story.safety_status,
        safety=story.safety_report,
        text=story.text,
        characters=[CharacterRef(id=c.id, name=c.name, type=c.type) for c in story.characters],
        adventure=adventure_ref(story),
        plot_cards=[p.text for p in story.plot_cards],
    )


def adventure_ref(story: Story) -> AdventureRef | None:
    adventure = story.adventure
    if adventure is None:
        return None
    return AdventureRef(id=adventure.id, title=adventure.title, chapter=story.chapter, chapter_count=adventure.chapter_count)


def placeholder_title(names: list[str]) -> str:
    if len(names) == 1:
        return f"A story with {names[0]}"
    return f"A story with {', '.join(names[:-1])} and {names[-1]}"


CHECK_FAILED = "The safety check couldn't run this time, so please read this story before sharing it."

DAILY_LIMIT_MESSAGE = (
    "That's all the new stories for today. Come back tomorrow for more, "
    "or read one of your saved stories."
)


def check_daily_limit(session: Session) -> None:
    """Each story started and each agent run counts (a run writes one chapter of an adventure).
    An adventure's planned chapters don't count until a run writes them."""
    limit = get_settings().max_stories_per_day
    if limit is None:
        return
    since = utc_now() - timedelta(hours=24)
    stories = session.exec(
        select(func.count()).select_from(Story).where(Story.created_at >= since, Story.adventure_id.is_(None))
    ).one()
    runs = session.exec(select(func.count()).select_from(AgentRun).where(AgentRun.created_at >= since)).one()
    if stories + runs >= limit:
        raise HTTPException(429, DAILY_LIMIT_MESSAGE)


@router.post("", response_model=StoryRead, status_code=201)
def create_story(payload: StoryCreate, session: Session = Depends(get_session)) -> StoryRead:
    check_daily_limit(session)
    ids = list(dict.fromkeys(payload.character_ids))
    characters = session.exec(select(Character).where(Character.id.in_(ids))).all()
    found = {c.id for c in characters}
    missing = [i for i in ids if i not in found]
    if missing:
        raise HTTPException(404, f"Unknown character ids: {missing}")

    by_id = {c.id: c for c in characters}
    ordered = [by_id[i] for i in ids]
    story = Story(
        title=placeholder_title([c.name for c in ordered]), bedtime=payload.bedtime, characters=ordered
    )
    session.add(story)
    session.commit()
    session.refresh(story)
    return to_story_read(story)


@router.get("", response_model=list[StorySummary])
def list_stories(session: Session = Depends(get_session)) -> list[StorySummary]:
    # Newest first, with an adventure's chapters together and in order (at the adventure's place).
    started = func.coalesce(Adventure.created_at, Story.created_at)
    stories = session.exec(
        select(Story).outerjoin(Adventure).order_by(started.desc(), Story.chapter, Story.id.desc())
    ).all()
    return [StorySummary(**to_story_read(s).model_dump()) for s in stories]


@router.get("/{story_id}", response_model=StoryRead)
def get_story(story_id: int, session: Session = Depends(get_session)) -> StoryRead:
    story = session.get(Story, story_id)
    if story is None:
        raise HTTPException(404, "Story not found")
    return to_story_read(story)


@router.patch("/{story_id}", response_model=StoryRead)
def update_story(story_id: int, payload: StoryUpdate, session: Session = Depends(get_session)) -> StoryRead:
    story = session.get(Story, story_id)
    if story is None:
        raise HTTPException(404, "Story not found")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if story.text is None and ("text" in changes or "verified" in changes):
        raise HTTPException(409, "This story has not been written yet")

    if "title" in changes:
        story.title = changes["title"]
    if "text" in changes:
        story.text = changes["text"]
        story.word_count = count_words(story.text)
        story.reading_minutes = reading_minutes(story.word_count)
    if "favourite" in changes:
        story.favourite = changes["favourite"]
    # Verifying is the parent's sign-off, whatever the AI's check said. A story the check flagged
    # keeps that history: needs_review becomes approved, and goes back if the parent undoes it.
    if changes.get("verified") is True and story.status != StoryStatus.verified:
        story.status = StoryStatus.verified
        story.verified_at = utc_now()
        if story.safety_status == SafetyStatus.needs_review:
            story.safety_status = SafetyStatus.approved
    elif changes.get("verified") is False and story.status == StoryStatus.verified:
        story.status = StoryStatus.written
        story.verified_at = None
        if story.safety_status == SafetyStatus.approved:
            story.safety_status = SafetyStatus.needs_review

    session.add(story)
    session.commit()
    session.refresh(story)
    return to_story_read(story)


@router.delete("/{story_id}", status_code=204)
def delete_story(story_id: int, session: Session = Depends(get_session)) -> Response:
    story = session.get(Story, story_id)
    if story is None:
        raise HTTPException(404, "Story not found")
    session.delete(story)  # SQLAlchemy also removes its character links
    session.commit()
    return Response(status_code=204)


@router.get("/{story_id}/stream")
def stream_story(
    story_id: int, request: Request, session: Session = Depends(get_session)
) -> StreamingResponse:
    story = session.get(Story, story_id)
    if story is None:
        raise HTTPException(404, "Story not found")
    if story.status != StoryStatus.planned:
        raise HTTPException(409, "This story has already been written")
    if story.adventure_id is not None:
        raise HTTPException(409, "This is a chapter of an adventure: the adventure agent writes it")
    child = session.exec(select(ChildProfile)).first()
    if child is None:
        raise HTTPException(409, "Set up a child profile first")

    everyone = session.exec(select(Character)).all()
    # Every new story is compared with the family's stories so far, so none repeats or resembles another.
    told = session.exec(
        select(Story)
        .where(Story.status != StoryStatus.planned, Story.id != story.id)
        .order_by(Story.created_at.desc(), Story.id.desc())
        .limit(EARLIER_STORIES)
    ).all()
    earlier = [safety.digest(s) for s in told]
    messages = build_story_messages(
        child,
        list(story.characters),
        bedtime=story.bedtime,
        others=everyone,
        plot=random.choice(PLOTS),
        earlier=earlier,
    )
    engine = request.app.state.engine
    bedtime = story.bedtime
    # Plain copies for the check, which runs after this request's database session has closed.
    hero = ChildProfile(name=child.name, age=child.age, favourite_things=list(child.favourite_things))
    cast = [
        Character(name=c.name, type=c.type, description=c.description, traits=list(c.traits), rules=list(c.rules))
        for c in story.characters
    ]

    # One Langfuse trace for this story: the writing, the check, and any rewrite.
    trace = tracing.Trace("story", details={"story_id": story_id, "bedtime": bedtime})

    async def stream_words(prompt: list[dict], parts: list[str], step: str):
        words = words_from_chunks(llm.stream_text(prompt, trace=trace.at(step)))
        async for word in with_keepalive(words, KEEPALIVE_SECONDS):
            if word is None:
                yield KEEPALIVE
                continue
            parts.append(word)
            yield sse("word", {"text": word})

    async def run_check(title: str | None, body: str, attempts: list[safety.Attempt]):
        yield sse("checking", {})
        result = None
        try:
            check = safety.check_story(title, body, hero, cast, bedtime=bedtime, earlier=earlier, trace=trace)
            async for item in await_with_keepalive(check, KEEPALIVE_SECONDS):
                if item is None:
                    yield KEEPALIVE
                else:
                    result = item
        except Exception:
            logger.exception("Safety check failed for story %s", story_id)
        attempts.append(result or safety.unchecked(body, CHECK_FAILED))

    async def events():
        try:
            async for event in write_and_check():
                yield event
        finally:
            await tracing.flush(trace)  # before Lambda freezes the process

    async def write_and_check():
        parts: list[str] = []
        try:
            async for event in stream_words(messages, parts, "write"):
                yield event
        except Exception:
            logger.exception("Story generation failed for story %s", story_id)
            yield sse("error", {"message": "The story could not be written. Please try again."})
            return

        title, body = split_title("".join(parts))
        if not body:
            yield sse("error", {"message": "The story came back empty. Please try again."})
            return

        # The safety and age check. A story that fails is rewritten once with the problems as
        # feedback; if the rewrite fails too, it's saved but flagged for a parent to read first.
        attempts: list[safety.Attempt] = []
        async for event in run_check(title, body, attempts):
            yield event
        first = attempts[0]
        if not first.passed and first.scariness is not None:  # checked and failed (not "couldn't check")
            yield sse("rewriting", {"problems": first.problems})
            again: list[str] = []
            try:
                rewrite = safety.build_rewrite_messages(messages, title, body, first.problems)
                async for event in stream_words(rewrite, again, "rewrite"):
                    yield event
                new_title, new_body = split_title("".join(again))
                if not new_body:
                    raise ValueError("empty rewrite")
            except Exception:
                logger.exception("Rewrite failed for story %s; keeping the first version", story_id)
            else:
                async for event in run_check(new_title, new_body, attempts):
                    yield event
                # Keep whichever version is safer: the rewrite unless it somehow scored worse.
                if attempts[-1].passed or (attempts[-1].scariness or 5) <= (first.scariness or 5):
                    title, body = new_title or title, new_body

        if first.passed:
            status = SafetyStatus.passed
        elif len(attempts) > 1 and attempts[-1].passed:
            status = SafetyStatus.rewritten
        else:
            status = SafetyStatus.needs_review

        # Saved only once the whole story has arrived and been checked. A failed or abandoned
        # stream leaves the story as "planned", so nothing half-written is kept.
        with Session(engine) as save_session:
            saved = save_session.get(Story, story_id)
            if saved is None:  # deleted while it was being written
                yield sse("error", {"message": "This story was deleted while it was being written."})
                return
            saved.title = title or saved.title
            saved.text = body
            saved.word_count = count_words(body)
            saved.reading_minutes = reading_minutes(saved.word_count)
            saved.status = StoryStatus.written
            saved.safety_status = status
            saved.safety_report = safety.report(attempts)
            save_session.add(saved)
            save_session.commit()
        yield sse("done", {"id": story_id, "title": title, "safety": status.value})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
