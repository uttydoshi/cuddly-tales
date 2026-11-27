from collections.abc import Sequence

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db import get_session
from app.models import Character
from app.schemas import CharacterRead

router = APIRouter(prefix="/api/characters", tags=["characters"])


@router.get("", response_model=list[CharacterRead])
def list_characters(session: Session = Depends(get_session)) -> Sequence[Character]:
    return session.exec(select(Character).order_by(Character.id)).all()
