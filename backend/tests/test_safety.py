"""The safety and age check: its rules, the judge's verdict, and the write → check → rewrite flow."""

import asyncio

import pytest
from sqlmodel import Session

from app.models import Character, CharacterType, ChildProfile, SafetyStatus, Story
from app.routers.stories import CHECK_FAILED
from app.services import llm, safety

GOOD_BODY = " ".join(["Minnie chased her ball across the garden."] * 60)  # 420 words


def child(age: int = 3) -> ChildProfile:
    return ChildProfile(name="Mira", age=age, favourite_things=[])


MINNIE = Character(
    name="Minnie",
    type=CharacterType.family,
    description="A toy poodle obsessed with her ball.",
    rules=["Chases her ball at least once per story."],
)


def verdict(**overrides) -> dict:
    """A judge reply that passes, with any field changed."""
    base = {
        "scariness": 1,
        "reading_level_ok": True,
        "ending_ok": True,
        "characters_stay_themselves": True,
        "rules": [{"character": "Minnie", "rule": "Chases her ball at least once per story.", "followed": True}],
        "problems": [],
    }
    return base | overrides


def fake_judge(monkeypatch, reply: dict) -> list[list[dict]]:
    calls: list[list[dict]] = []

    async def complete_json(messages, schema, *, name, **kwargs):
        calls.append(messages)
        return reply

    monkeypatch.setattr(llm, "complete_json", complete_json)
    return calls


def check(title, body, age=3, bedtime=True):
    return asyncio.run(safety.check_story(title, body, child(age), [MINNIE], bedtime=bedtime))


# --- Rules that need no model ---


def test_rules_pass_a_story_of_the_right_length():
    assert safety.rule_problems("The Ball", GOOD_BODY, age=3) == []


def test_rules_catch_length_for_the_age():
    assert "Too short for age 3" in safety.rule_problems("T", "Minnie chased her ball.", age=3)[0]
    assert "Too long for age 3" in safety.rule_problems("T", GOOD_BODY * 3, age=3)[0]
    # 420 words is too short for a 6-year-old (aim 600-900).
    assert "Too short for age 6" in safety.rule_problems("T", GOOD_BODY, age=6)[0]


def test_rules_need_a_title():
    assert safety.rule_problems(None, GOOD_BODY, age=3) == ["The story has no title."]


def test_rules_catch_frightening_words_but_not_parts_of_words():
    problems = safety.rule_problems("T", GOOD_BODY + " The wolf was terrified of the KNIFE.", age=3)
    assert problems == ["Uses words too frightening for a young child: knife, terrified."]
    # "studied" contains "die", "skill" contains "kill": whole words only.
    assert safety.rule_problems("T", GOOD_BODY + " Tosia studied her skill.", age=3) == []


# --- The judge ---


def test_a_gentle_story_that_keeps_the_rules_passes(monkeypatch):
    calls = fake_judge(monkeypatch, verdict())
    attempt = check("The Ball", GOOD_BODY)
    assert attempt.passed
    assert attempt.problems == []
    # The judge is told the child's age, the characters' rules and that it's a bedtime story.
    prompt = calls[0][1]["content"]
    assert "aged 3" in prompt and "Chases her ball at least once per story." in prompt and "bedtime" in prompt


def test_too_scary_fails(monkeypatch):
    fake_judge(monkeypatch, verdict(scariness=3, problems=["The wolf chase is too tense."]))
    attempt = check("The Ball", GOOD_BODY)
    assert not attempt.passed
    assert attempt.problems == ["The wolf chase is too tense."]


def test_a_broken_character_rule_fails_and_is_explained(monkeypatch):
    rules = [{"character": "Minnie", "rule": "Chases her ball at least once per story.", "followed": False}]
    fake_judge(monkeypatch, verdict(rules=rules))
    attempt = check("The Ball", GOOD_BODY)
    assert not attempt.passed
    assert attempt.problems == ["Minnie doesn't follow their rule: Chases her ball at least once per story."]


def test_a_character_given_a_role_they_dont_have_fails(monkeypatch):
    # The "Babcia Tosia" bug: a cat called a grandma.
    fake_judge(
        monkeypatch,
        verdict(characters_stay_themselves=False, problems=["Tosia is called Babcia, but she is a cat."]),
    )
    attempt = check("The Ball", GOOD_BODY)
    assert not attempt.passed
    assert attempt.problems == ["Tosia is called Babcia, but she is a cat."]


def test_rule_problems_come_first_and_fail_even_if_the_judge_is_happy(monkeypatch):
    fake_judge(monkeypatch, verdict())
    attempt = check("The Ball", "Too short.")
    assert not attempt.passed
    assert attempt.problems[0].startswith("Too short for age 3")


def test_json_replies_are_read_with_or_without_a_fence():
    assert llm.parse_json('{"a": 1}') == {"a": 1}
    assert llm.parse_json('```json\n{"a": 1}\n```') == {"a": 1}


# --- The flow: write, check, rewrite once, check again, save ---

FIRST = ["# The Wolf\n\n", "A ", "big ", "wolf ", "growled."]
REWRITE = ["# The Ball\n\n", "Minnie ", "chased ", "her ", "ball."]


def fake_writer(monkeypatch, *versions):
    """Each call to the story model streams the next version."""
    queue = list(versions)
    prompts: list[list[dict]] = []

    async def stream_text(messages, **kwargs):
        prompts.append(messages)
        version = queue.pop(0)
        if isinstance(version, Exception):
            raise version
        for chunk in version:
            yield chunk

    monkeypatch.setattr(llm, "stream_text", stream_text)
    return prompts


def fake_checks(monkeypatch, *results):
    """Each safety check returns the next result (an Attempt, or an exception to raise)."""
    queue = list(results)

    async def check_story(title, body, child, characters, *, bedtime):
        result = queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(safety, "check_story", check_story)


PASS = safety.Attempt(passed=True, word_count=4, scariness=1)
SCARY = safety.Attempt(passed=False, word_count=4, scariness=4, problems=["The growling wolf is too scary."])


@pytest.fixture
def story_id(client):
    ids = {c["name"]: c["id"] for c in client.get("/api/characters").json()}
    return client.post("/api/stories", json={"character_ids": [ids["Minnie"]], "bedtime": True}).json()["id"]


def stream(client, story_id):
    from tests.test_stories import parse_events

    return parse_events(client.get(f"/api/stories/{story_id}/stream").text)


def saved(engine, story_id) -> Story:
    with Session(engine) as session:
        return session.get(Story, story_id)


def test_a_story_that_passes_is_saved_as_passed(client, engine, story_id, monkeypatch):
    fake_writer(monkeypatch, REWRITE)
    fake_checks(monkeypatch, PASS)
    events = stream(client, story_id)
    names = [name for name, _ in events]
    assert "checking" in names and "rewriting" not in names
    assert events[-1] == ("done", {"id": story_id, "title": "The Ball", "safety": "passed"})
    story = saved(engine, story_id)
    assert story.safety_status == SafetyStatus.passed
    assert len(story.safety_report["attempts"]) == 1


def test_a_failed_story_is_rewritten_once_with_the_problems(client, engine, story_id, monkeypatch):
    prompts = fake_writer(monkeypatch, FIRST, REWRITE)
    fake_checks(monkeypatch, SCARY, PASS)
    events = stream(client, story_id)

    assert ("rewriting", {"problems": ["The growling wolf is too scary."]}) in events
    assert events[-1] == ("done", {"id": story_id, "title": "The Ball", "safety": "rewritten"})
    # The rewrite request carries the first version and what to fix.
    assert "A big wolf growled." in prompts[1][-2]["content"]
    assert "The growling wolf is too scary." in prompts[1][-1]["content"]

    story = saved(engine, story_id)
    assert story.text == "Minnie chased her ball."
    assert story.safety_status == SafetyStatus.rewritten
    assert [a["passed"] for a in story.safety_report["attempts"]] == [False, True]


def test_a_story_that_fails_twice_is_flagged_for_a_parent(client, engine, story_id, monkeypatch):
    fake_writer(monkeypatch, FIRST, REWRITE)
    fake_checks(monkeypatch, SCARY, safety.Attempt(passed=False, word_count=4, scariness=2, problems=["Too short."]))
    events = stream(client, story_id)
    assert events[-1][1]["safety"] == "needs_review"
    story = saved(engine, story_id)
    assert story.safety_status == SafetyStatus.needs_review
    assert story.text == "Minnie chased her ball."  # the gentler rewrite is kept
    assert len(story.safety_report["attempts"]) == 2


def test_if_the_check_cant_run_the_story_is_flagged_not_trusted(client, engine, story_id, monkeypatch):
    fake_writer(monkeypatch, REWRITE)
    fake_checks(monkeypatch, RuntimeError("judge down"))
    events = stream(client, story_id)
    assert "rewriting" not in [name for name, _ in events]
    assert events[-1][1]["safety"] == "needs_review"
    story = saved(engine, story_id)
    assert story.safety_report["attempts"][0]["problems"] == [CHECK_FAILED]


def test_if_the_rewrite_fails_the_first_version_is_kept_and_flagged(client, engine, story_id, monkeypatch):
    fake_writer(monkeypatch, FIRST, RuntimeError("provider down"))
    fake_checks(monkeypatch, SCARY)
    events = stream(client, story_id)
    assert events[-1][1]["safety"] == "needs_review"
    story = saved(engine, story_id)
    assert story.text == "A big wolf growled."
    assert story.status == "written"


def test_the_story_api_reports_the_check(client, story_id, monkeypatch):
    fake_writer(monkeypatch, FIRST, REWRITE)
    fake_checks(monkeypatch, SCARY, PASS)
    stream(client, story_id)
    story = client.get(f"/api/stories/{story_id}").json()
    assert story["safety_status"] == "rewritten"
    assert story["safety"]["attempts"][0]["problems"] == ["The growling wolf is too scary."]
    assert client.get("/api/stories").json()[0]["safety_status"] == "rewritten"


def test_a_parent_can_approve_a_flagged_story(client, story_id, monkeypatch):
    fake_writer(monkeypatch, REWRITE)
    fake_checks(monkeypatch, RuntimeError("judge down"))
    stream(client, story_id)
    response = client.patch(f"/api/stories/{story_id}", json={"approve": True})
    assert response.status_code == 200
    assert response.json()["safety_status"] == "approved"


def test_only_a_flagged_story_can_be_approved(client, story_id, monkeypatch):
    fake_writer(monkeypatch, REWRITE)
    fake_checks(monkeypatch, PASS)
    stream(client, story_id)
    assert client.patch(f"/api/stories/{story_id}", json={"approve": True}).status_code == 409
