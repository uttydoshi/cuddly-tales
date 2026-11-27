import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import Character, ChildProfile, Story, StoryStatus
from app.schemas import CharacterRef, StoryCreate, StoryRead
from app.services import llm
from app.services.story_prompt import build_story_messages
from app.services.story_stream import count_words, reading_minutes, split_title, sse, words_from_chunks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stories", tags=["stories"])


def to_story_read(story: Story) -> StoryRead:
    return StoryRead(
        id=story.id,
        title=story.title,
        status=story.status,
        word_count=story.word_count,
        reading_minutes=story.reading_minutes,
        created_at=story.created_at,
        read_at=story.read_at,
        text=story.text,
        characters=[CharacterRef(id=c.id, name=c.name) for c in story.characters],
    )


def placeholder_title(names: list[str]) -> str:
    if len(names) == 1:
        return f"A story with {names[0]}"
    return f"A story with {', '.join(names[:-1])} and {names[-1]}"


@router.post("", response_model=StoryRead, status_code=201)
def create_story(payload: StoryCreate, session: Session = Depends(get_session)) -> StoryRead:
    ids = list(dict.fromkeys(payload.character_ids))
    characters = session.exec(select(Character).where(Character.id.in_(ids))).all()
    found = {c.id for c in characters}
    missing = [i for i in ids if i not in found]
    if missing:
        raise HTTPException(404, f"Unknown character ids: {missing}")

    by_id = {c.id: c for c in characters}
    ordered = [by_id[i] for i in ids]
    story = Story(title=placeholder_title([c.name for c in ordered]), characters=ordered)
    session.add(story)
    session.commit()
    session.refresh(story)
    return to_story_read(story)


@router.get("/{story_id}/stream")
def stream_story(
    story_id: int, request: Request, session: Session = Depends(get_session)
) -> StreamingResponse:
    story = session.get(Story, story_id)
    if story is None:
        raise HTTPException(404, "Story not found")
    if story.status != StoryStatus.planned:
        raise HTTPException(409, "This story has already been written")
    child = session.exec(select(ChildProfile)).first()
    if child is None:
        raise HTTPException(409, "Set up a child profile first")

    messages = build_story_messages(child, list(story.characters))
    engine = request.app.state.engine

    async def events():
        parts: list[str] = []
        try:
            async for word in words_from_chunks(llm.stream_text(messages)):
                parts.append(word)
                yield sse("word", {"text": word})
        except Exception:
            logger.exception("Story generation failed for story %s", story_id)
            yield sse("error", {"message": "The story could not be written. Please try again."})
            return

        title, body = split_title("".join(parts))
        if not body:
            yield sse("error", {"message": "The story came back empty. Please try again."})
            return

        # Saved only once the whole story has arrived. A failed or abandoned
        # stream leaves the story as "planned", so nothing half-written is kept.
        with Session(engine) as save_session:
            saved = save_session.get(Story, story_id)
            saved.title = title or saved.title
            saved.text = body
            saved.word_count = count_words(body)
            saved.reading_minutes = reading_minutes(saved.word_count)
            saved.status = StoryStatus.written
            save_session.add(saved)
            save_session.commit()
        yield sse("done", {"id": story_id, "title": title})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
