from app.models import Character, CharacterType, ChildProfile
from app.services.story_prompt import build_story_messages, word_range

CHILD = ChildProfile(name="Mira", age=3, favourite_things=["bubbles"])
MINNIE = Character(
    name="Minnie",
    type=CharacterType.family,
    description="A toy poodle obsessed with her ball.",
    traits=["bouncy"],
    rules=["Chases her ball at least once per story."],
)
MAVERICK = Character(
    name="Maverick",
    type=CharacterType.family,
    description="A lazy couch king.",
    rules=["Stays on the couch unless food is involved."],
)


def test_prompt_includes_child_characters_and_rules():
    system, user = build_story_messages(CHILD, [MINNIE, MAVERICK])
    assert system["role"] == "system"
    assert "Nothing frightening" in system["content"]
    assert "Mira, aged 3" in user["content"]
    assert "bubbles" in user["content"]
    assert "Rule: Chases her ball at least once per story." in user["content"]
    assert "Rule: Stays on the couch unless food is involved." in user["content"]
    assert "300-600 words" in user["content"]


def test_word_range_follows_age_and_falls_back_to_age_3():
    assert word_range(3) == (300, 600)
    assert word_range(6) == (600, 900)
    assert word_range(9) == (300, 600)


def test_prompt_allows_only_italics_for_foreign_words():
    system, _ = build_story_messages(CHILD, [MINNIE])
    assert "*single asterisks*" in system["content"]
    assert "No other headings, lists, bold or markdown." in system["content"]


def test_bedtime_story_asks_for_a_sleepy_ending():
    _, user = build_story_messages(CHILD, [MINNIE], bedtime=True)
    assert "bedtime story" in user["content"]
    assert "ready for bed" in user["content"]


def test_anytime_story_does_not_send_anyone_to_sleep():
    system, user = build_story_messages(CHILD, [MINNIE])
    assert "not bedtime" in user["content"]
    assert "ready for bed" not in user["content"]
    assert "bedtime stories" not in system["content"]


def test_system_prompt_is_the_same_for_every_story():
    """Everything that varies goes in the user message, so the system prompt can be cached."""
    bedtime_system, _ = build_story_messages(CHILD, [MINNIE], bedtime=True)
    anytime_system, _ = build_story_messages(CHILD, [MAVERICK])
    assert bedtime_system == anytime_system
