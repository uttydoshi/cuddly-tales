from sqlmodel import Session, select

from app.models import Character, ChildProfile
from app.seed import seed_if_empty


def test_startup_seeds_demo_family(client, engine):
    with Session(engine) as session:
        child = session.exec(select(ChildProfile)).one()
        names = {c.name for c in session.exec(select(Character))}
    assert (child.name, child.age) == ("Mira", 3)
    assert {"Minnie", "Maverick", "Tosia", "Diggles", "Baba Yaga"} <= names
    assert len(names) == 10


def test_seed_does_not_duplicate(client, engine):
    with Session(engine) as session:
        seed_if_empty(session)
        assert len(session.exec(select(ChildProfile)).all()) == 1
        assert len(session.exec(select(Character)).all()) == 10
