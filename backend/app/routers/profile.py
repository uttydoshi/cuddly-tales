from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import ChildProfile
from app.schemas import ChildProfileRead

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ChildProfileRead)
def get_profile(session: Session = Depends(get_session)) -> ChildProfile:
    child = session.exec(select(ChildProfile)).first()
    if child is None:
        raise HTTPException(404, "No child profile yet")
    return child
