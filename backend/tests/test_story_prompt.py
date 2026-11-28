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


TOSIA = Character(
    id=3,
    name="Tosia",
    type=CharacterType.original,
    description="A tidy, cosy cat who loves routines.",
)
DIGGLES = Character(
    id=4,
    name="Diggles",
    type=CharacterType.original,
    description="A cheeky wombat.",
    rules=["Digs at least one hole, often in Tosia's garden."],
)


def test_someone_mentioned_in_a_rule_but_not_in_the_story_is_described():
    """Diggles' rule mentions Tosia's garden; without saying Tosia is a cat, the model
    turned her into "Babcia Tosia", a grandma."""
    _, user = build_story_messages(CHILD, [DIGGLES], others=[MINNIE, TOSIA, DIGGLES])
    content = user["content"]
    assert "Also mentioned in the rules above, but not in this story" in content
    assert "- Tosia: A tidy, cosy cat who loves routines." in content
    assert "- Minnie:" not in content.split("Also mentioned")[1]  # not mentioned, so not listed


def test_no_also_mentioned_section_when_they_are_in_the_story_or_not_mentioned():
    _, both = build_story_messages(CHILD, [DIGGLES, TOSIA], others=[TOSIA, DIGGLES])
    _, unrelated = build_story_messages(CHILD, [MINNIE], others=[TOSIA, DIGGLES])
    assert "Also mentioned" not in both["content"]
    assert "Also mentioned" not in unrelated["content"]


def test_characters_keep_who_they_are():
    system, _ = build_story_messages(CHILD, [MINNIE])
    assert "a cat stays a cat" in system["content"]
    assert "Babcia" in system["content"]


def test_mentions_matches_whole_names_and_names_without_the():
    from app.services.story_prompt import mentions

    wolf = Character(name="The Big Bad Wolf", type=CharacterType.folklore, description="Grumpy.")
    friend = Character(name="X", type=CharacterType.custom, description="Friends with Big Bad Wolf.")
    assert mentions(friend, wolf.name)
    assert not mentions(DIGGLES, "Tos")  # part of a word doesn't count


def test_running_jokes_are_moments_not_the_plot():
    system, _ = build_story_messages(CHILD, [MINNIE])
    assert "never the main plot" in system["content"]


def test_prompt_names_the_kind_of_story_and_avoids_earlier_ones():
    earlier = [("Mira and the Lost Mortar", "Baba Yaga loses her mortar and Mira helps find it.")]
    _, user = build_story_messages(CHILD, [MINNIE], plot="cooking or baking something", earlier=earlier)
    assert "The kind of story: cooking or baking something." in user["content"]
    assert "not a repeat, and not similar either" in user["content"]
    assert "- Mira and the Lost Mortar: Baba Yaga loses her mortar and Mira helps find it." in user["content"]


def test_no_variety_section_without_a_plot_or_recent_stories():
    _, user = build_story_messages(CHILD, [MINNIE])
    assert "kind of story" not in user["content"] and "already told" not in user["content"]
