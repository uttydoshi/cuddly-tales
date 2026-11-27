from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from app.db import get_session
from app.models import Character
from app.schemas import CharacterCreate, CharacterRead, CharacterUpdate

router = APIRouter(prefix="/api/characters", tags=["characters"])


def get_character_or_404(character_id: int, session: Session) -> Character:
    character = session.get(Character, character_id)
    if character is None:
        raise HTTPException(404, "Character not found")
    return character


@router.get("", response_model=list[CharacterRead])
def list_characters(session: Session = Depends(get_session)) -> Sequence[Character]:
    return session.exec(select(Character).order_by(Character.id)).all()


@router.post("", response_model=CharacterRead, status_code=201)
def create_character(payload: CharacterCreate, session: Session = Depends(get_session)) -> Character:
    character = Character(**payload.model_dump())
    session.add(character)
    session.commit()
    session.refresh(character)
    return character


@router.get("/{character_id}", response_model=CharacterRead)
def get_character(character_id: int, session: Session = Depends(get_session)) -> Character:
    return get_character_or_404(character_id, session)


@router.patch("/{character_id}", response_model=CharacterRead)
def update_character(
    character_id: int, payload: CharacterUpdate, session: Session = Depends(get_session)
) -> Character:
    character = get_character_or_404(character_id, session)
    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(character, field, value)
    session.add(character)
    session.commit()
    session.refresh(character)
    return character


@router.delete("/{character_id}", status_code=204)
def delete_character(character_id: int, session: Session = Depends(get_session)) -> Response:
    """Delete for good. Stories keep their text; the character leaves their cast list."""
    character = get_character_or_404(character_id, session)
    session.delete(character)  # SQLAlchemy also removes its story links
    session.commit()
    return Response(status_code=204)
