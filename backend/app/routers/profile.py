from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import ChildProfile
from app.schemas import ChildProfileRead, ChildProfileUpdate

router = APIRouter(prefix="/api/profile", tags=["profile"])


def get_child_or_404(session: Session) -> ChildProfile:
    child = session.exec(select(ChildProfile)).first()
    if child is None:
        raise HTTPException(404, "No child profile yet")
    return child


@router.get("", response_model=ChildProfileRead)
def get_profile(session: Session = Depends(get_session)) -> ChildProfile:
    return get_child_or_404(session)


@router.put("", response_model=ChildProfileRead)
def update_profile(payload: ChildProfileUpdate, session: Session = Depends(get_session)) -> ChildProfile:
    """One child per deployment for now, so this replaces the single profile."""
    child = get_child_or_404(session)
    child.name = payload.name
    child.age = payload.age
    child.favourite_things = payload.favourite_things
    session.add(child)
    session.commit()
    session.refresh(child)
    return child
