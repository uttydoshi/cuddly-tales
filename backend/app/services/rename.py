"""Changing the child's name in stories already written, and in the characters.

Every story stars the child by name, so when a parent changes it (a typo, a nickname, or the
demo family handed over to a real one) the old stories should say the new name too. Characters
can mention the child as well (Diggles is "fiercely loyal to Mira"), and new stories are written
from them, so they change too. Only the
whole name is changed, in its usual and shouted forms ("Mira", "Mira's", "MIRA!"), so a word that
merely contains it ("Miranda", "admiral") is left alone.
"""

import re

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from app.models import Character, Story


def replace_name(text: str, old: str, new: str) -> str:
    for before, after in ((old, new), (old.upper(), new.upper())):
        text = re.sub(rf"(?<!\w){re.escape(before)}(?!\w)", lambda _: after, text)
    return text


def rename_child(session: Session, old: str, new: str) -> int:
    """Change the child's name in every character, and in every story's title, text and saved
    summaries. Returns how many stories changed. The caller commits."""
    if old == new:
        return 0
    for character in session.exec(select(Character)).all():
        description = replace_name(character.description, old, new)
        traits = [replace_name(t, old, new) for t in character.traits]
        rules = [replace_name(r, old, new) for r in character.rules]
        if (description, traits, rules) != (character.description, character.traits, character.rules):
            character.description, character.traits, character.rules = description, traits, rules
            session.add(character)

    changed = 0
    for story in session.exec(select(Story)).all():
        title = replace_name(story.title, old, new)
        text = replace_name(story.text, old, new) if story.text else story.text
        report = story.safety_report
        attempts = (report or {}).get("attempts") or []
        summaries = [a.get("summary") for a in attempts]
        renamed = [replace_name(s, old, new) if s else s for s in summaries]
        if title == story.title and text == story.text and renamed == summaries:
            continue
        story.title, story.text = title, text
        if renamed != summaries:
            for attempt, summary in zip(attempts, renamed, strict=True):
                attempt["summary"] = summary
            flag_modified(story, "safety_report")
        session.add(story)
        changed += 1
    return changed
