from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import ChildProfile
from app.schemas import ChildProfileRead, ChildProfileSaved, ChildProfileUpdate
from app.services.rename import rename_child

router = APIRouter(prefix="/api/profile", tags=["profile"])


def get_child_or_404(session: Session) -> ChildProfile:
    child = session.exec(select(ChildProfile)).first()
    if child is None:
        raise HTTPException(404, "No child profile yet")
    return child


@router.get("", response_model=ChildProfileRead)
def get_profile(session: Session = Depends(get_session)) -> ChildProfile:
    return get_child_or_404(session)


@router.put("", response_model=ChildProfileSaved)
def update_profile(payload: ChildProfileUpdate, session: Session = Depends(get_session)) -> ChildProfileSaved:
    """One child per deployment for now, so this replaces the single profile. A new name is
    also changed in every story already written, so the hero keeps their name."""
    child = get_child_or_404(session)
    renamed = rename_child(session, child.name, payload.name)
    child.name = payload.name
    child.age = payload.age
    child.favourite_things = payload.favourite_things
    session.add(child)
    session.commit()
    session.refresh(child)
    saved = ChildProfileRead.model_validate(child, from_attributes=True)
    return ChildProfileSaved(**saved.model_dump(), stories_renamed=renamed)
