"""Adventures, and the agent runs that plan and write them.

Starting a run and watching it are two requests: POST creates the run (and checks the daily cap),
then the page opens GET .../stream, which does the work and streams each step as it happens.
A run that loses its page stops; its steps so far are kept.
"""

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import update
from sqlmodel import Session, select

from app.db import get_session
from app.models import (
    Adventure,
    AdventureStatus,
    AgentRun,
    AgentRunKind,
    AgentRunStatus,
    AgentStep,
    Character,
    ChildProfile,
    Story,
    StoryStatus,
    utc_now,
)
from app.routers.stories import KEEPALIVE_SECONDS, check_daily_limit
from app.schemas import AdventureCreate, AdventureRead, AgentRunRead, AgentStepRead, NextChapter, ChapterRead
from app.services import tracing
from app.services.adventure_agent import AdventureAgent, goal_for_next, goal_for_plan
from app.services.story_stream import KEEPALIVE, sse, with_keepalive

logger = logging.getLogger(__name__)

router = APIRouter(tags=["adventures"])

# A run still "running" after this long was cut off (Lambda stops a request at 5 minutes).
STALE_AFTER = timedelta(minutes=6)


def chapters_of(session: Session, adventure_id: int) -> list[Story]:
    return list(session.exec(select(Story).where(Story.adventure_id == adventure_id).order_by(Story.chapter)).all())


def to_adventure_read(session: Session, adventure: Adventure) -> AdventureRead:
    return AdventureRead(
        id=adventure.id,
        title=adventure.title,
        premise=adventure.premise,
        chapter_count=adventure.chapter_count,
        bedtime=adventure.bedtime,
        status=adventure.status,
        created_at=adventure.created_at,
        chapters=[
            ChapterRead(
                chapter=s.chapter,
                story_id=s.id,
                title=s.title,
                status=s.status,
                safety_status=s.safety_status,
                plot_cards=[p.text for p in s.plot_cards],
            )
            for s in chapters_of(session, adventure.id)
        ],
    )


def settle_if_stale(session: Session, run: AgentRun) -> AgentRun:
    """A run whose request was killed never gets to say so; call it stopped once it's clearly over."""
    created = run.created_at if run.created_at.tzinfo else run.created_at.replace(tzinfo=utc_now().tzinfo)
    if run.status == AgentRunStatus.running and utc_now() - created > STALE_AFTER:
        run.status = AgentRunStatus.stopped
        run.error = "Stopped before finishing."
        run.finished_at = utc_now()
        session.add(run)
        session.commit()
        session.refresh(run)
    return run


def to_run_read(session: Session, run: AgentRun) -> AgentRunRead:
    steps = session.exec(select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.position)).all()
    adventure = session.get(Adventure, run.adventure_id) if run.adventure_id else None
    return AgentRunRead(
        id=run.id,
        kind=run.kind,
        goal=run.goal,
        status=run.status,
        trigger=run.trigger,
        error=run.error,
        created_at=run.created_at,
        finished_at=run.finished_at,
        adventure=to_adventure_read(session, adventure) if adventure else None,
        steps=[AgentStepRead.model_validate(s, from_attributes=True) for s in steps],
    )


def get_run_or_404(session: Session, run_id: int) -> AgentRun:
    run = session.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(404, "Agent run not found")
    return settle_if_stale(session, run)


@router.post("/api/adventures", response_model=AgentRunRead, status_code=201)
def plan_adventure(payload: AdventureCreate, session: Session = Depends(get_session)) -> AgentRunRead:
    """Start the agent on "Plan an N-chapter adventure". The page then opens the run's stream."""
    check_daily_limit(session)
    child = session.exec(select(ChildProfile)).first()
    if child is None:
        raise HTTPException(409, "Set up a child profile first")
    ids = list(dict.fromkeys(payload.character_ids))
    found = set(session.exec(select(Character.id).where(Character.id.in_(ids))).all()) if ids else set()
    missing = [i for i in ids if i not in found]
    if missing:
        raise HTTPException(404, f"Unknown character ids: {missing}")
    run = AgentRun(
        kind=AgentRunKind.plan,
        goal=goal_for_plan(child.name, payload.chapter_count),
        chapter_count=payload.chapter_count,
        bedtime=payload.bedtime,
        theme=payload.theme or None,
        character_ids=ids,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return to_run_read(session, run)


@router.get("/api/adventures", response_model=list[AdventureRead])
def list_adventures(session: Session = Depends(get_session)) -> list[AdventureRead]:
    adventures = session.exec(select(Adventure).order_by(Adventure.created_at.desc(), Adventure.id.desc())).all()
    return [to_adventure_read(session, a) for a in adventures]


@router.get("/api/adventures/{adventure_id}", response_model=AdventureRead)
def get_adventure(adventure_id: int, session: Session = Depends(get_session)) -> AdventureRead:
    adventure = session.get(Adventure, adventure_id)
    if adventure is None:
        raise HTTPException(404, "Adventure not found")
    return to_adventure_read(session, adventure)


@router.post("/api/adventures/{adventure_id}/next", response_model=AgentRunRead, status_code=201)
def write_next_chapter(
    adventure_id: int, payload: NextChapter | None = None, session: Session = Depends(get_session)
) -> AgentRunRead:
    """Start the agent on the adventure's next chapter (the scheduled job does the same each evening)."""
    adventure = session.get(Adventure, adventure_id)
    if adventure is None:
        raise HTTPException(404, "Adventure not found")
    planned = [s for s in chapters_of(session, adventure_id) if s.status == StoryStatus.planned]
    if adventure.status == AdventureStatus.finished or not planned:
        raise HTTPException(409, "Every chapter of this adventure has been written")
    busy = session.exec(
        select(AgentRun).where(
            AgentRun.adventure_id == adventure_id,
            AgentRun.status.in_([AgentRunStatus.pending, AgentRunStatus.running]),
        )
    ).all()
    if any(settle_if_stale(session, r).status in (AgentRunStatus.pending, AgentRunStatus.running) for r in busy):
        raise HTTPException(409, "The agent is already writing a chapter of this adventure")
    check_daily_limit(session)
    run = AgentRun(
        kind=AgentRunKind.next_chapter,
        goal=goal_for_next(planned[0].chapter, adventure.title),
        trigger=(payload.trigger if payload else "parent"),
        bedtime=adventure.bedtime,
        adventure_id=adventure_id,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return to_run_read(session, run)


@router.get("/api/agent-runs/{run_id}", response_model=AgentRunRead)
def get_run(run_id: int, session: Session = Depends(get_session)) -> AgentRunRead:
    return to_run_read(session, get_run_or_404(session, run_id))


@router.get("/api/agent-runs/{run_id}/stream")
def stream_run(run_id: int, request: Request, session: Session = Depends(get_session)) -> StreamingResponse:
    """Do the run, streaming each step as it starts and finishes. Only a run that hasn't started
    yet can be streamed, so reloading the page can't start the same work twice."""
    get_run_or_404(session, run_id)
    started = session.execute(
        update(AgentRun)
        .where(AgentRun.id == run_id, AgentRun.status == AgentRunStatus.pending)
        .values(status=AgentRunStatus.running)
    )
    session.commit()
    if started.rowcount != 1:
        raise HTTPException(409, "This run has already started")
    engine = request.app.state.engine
    agent = AdventureAgent(engine, run_id)

    async def events():
        try:
            async for step in with_keepalive(agent.run(), KEEPALIVE_SECONDS):
                if step is None:
                    yield KEEPALIVE
                else:
                    yield sse("step", AgentStepRead.model_validate(step, from_attributes=True).model_dump(mode="json"))
        except Exception:
            logger.exception("Agent run %s stream failed", run_id)
        with Session(engine) as done_session:
            run = to_run_read(done_session, done_session.get(AgentRun, run_id))
        yield sse("done", run.model_dump(mode="json"))
        await tracing.flush()  # after the parent has the result, before Lambda freezes the process

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
