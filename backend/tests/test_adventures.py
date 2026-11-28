"""The adventure agent, with a scripted model: each test says which tools the "model" calls, in
order, and checks what the tools did, what was saved, and what the parent would see."""

import json
from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.models import AgentRun, AgentRunKind, AgentRunStatus, Story, utc_now
from app.services import adventure_agent, llm, safety

CHAPTER = "# Sandcastle Day\n\n" + "Mira built a sandcastle with Minnie. " * 60


class ScriptedModel:
    """Plays back turns of (text, [(tool, arguments), ...]) and records what it was sent."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.seen: list[list[dict]] = []

    async def __call__(self, messages, tools, **kwargs):
        self.seen.append(list(messages))
        text, calls = self.turns.pop(0) if self.turns else ("All done.", [])
        tool_calls = [llm.ToolCall(id=f"call-{len(self.seen)}-{i}", name=n, arguments=a) for i, (n, a) in enumerate(calls)]
        return llm.AgentTurn(text=text, tool_calls=tool_calls, message={"role": "assistant", "content": text})

    def tool_results(self) -> list[dict]:
        """What the tools returned for the last turn that called any."""
        conversation = self.seen[-1] if self.seen else []
        replies = [i for i, m in enumerate(conversation) if m.get("role") == "assistant"]
        after = conversation[replies[-1] + 1 :] if replies else []
        return [json.loads(m["content"]) for m in after if m.get("role") == "tool"]


@pytest.fixture
def written(monkeypatch):
    """Every chapter comes back as CHAPTER; the prompts are kept."""
    prompts = []

    async def stream_text(messages, **kwargs):
        prompts.append(messages)
        yield CHAPTER

    monkeypatch.setattr(llm, "stream_text", stream_text)
    return prompts


def checks(monkeypatch, *results: bool):
    """The safety check passes or fails in this order (then passes)."""
    queue = list(results)

    async def check_story(title, body, child, characters, *, bedtime, earlier=()):
        passed = queue.pop(0) if queue else True
        problems = [] if passed else ["Too scary: make the waves gentle."]
        return safety.Attempt(passed=passed, word_count=len(body.split()), scariness=1 if passed else 3, problems=problems)

    monkeypatch.setattr(safety, "check_story", check_story)


@pytest.fixture
def cast(client):
    return {c["name"]: c["id"] for c in client.get("/api/characters").json()}


def plan_calls(cast, nights=3):
    return [
        ("Let me learn about Mira first.", [("get_child_profile", {}), ("list_characters", {}), ("get_previous_stories", {})]),
        (
            "Now I'll plan the nights.",
            [
                (
                    "create_plot_cards",
                    {
                        "title": "The Great Beach Day",
                        "premise": "Mira and friends build the biggest sandcastle ever.",
                        "nights": [
                            {
                                "title": f"Night {n}",
                                "character_ids": [cast["Minnie"], cast["Tosia"]],
                                "beats": [f"Beat {n}a", f"Beat {n}b", f"Beat {n}c"],
                            }
                            for n in range(1, nights + 1)
                        ],
                    },
                )
            ],
        ),
    ]


def run_agent(client, monkeypatch, turns, **body):
    model = ScriptedModel(turns)
    monkeypatch.setattr(llm, "complete_with_tools", model)
    run = client.post("/api/adventures", json={"nights": 3} | body).json()
    stream = client.get(f"/api/agent-runs/{run['id']}/stream").text
    return run["id"], model, events(stream)


def events(stream: str) -> list[tuple[str, dict]]:
    found = []
    for block in stream.split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if not line.startswith(":"))
        if "event" in lines:
            found.append((lines["event"], json.loads(lines["data"])))
    return found


def test_plan_run_plans_every_night_and_writes_the_first(client, monkeypatch, cast, written):
    checks(monkeypatch, True)
    turns = plan_calls(cast) + [
        ("Writing night 1.", [("write_chapter", {"night": 1})]),
        ("Checking it.", [("safety_check", {"night": 1})]),
        ("Saving it.", [("save_story", {"night": 1})]),
        ("Night 1 is ready to read.", []),
    ]
    run_id, _, streamed = run_agent(client, monkeypatch, turns, character_ids=[cast["Tosia"]])

    done = streamed[-1]
    assert done[0] == "done"
    assert done[1]["status"] == "finished"
    assert done[1]["goal"] == "Plan a 3-night adventure for Mira"

    run = client.get(f"/api/agent-runs/{run_id}").json()
    tools = [s["tool"] for s in run["steps"]]
    assert tools == [
        "message", "get_child_profile", "list_characters", "get_previous_stories",
        "message", "create_plot_cards",
        "message", "write_chapter", "message", "safety_check", "message", "save_story", "message",
    ]  # fmt: skip
    assert all(s["ok"] for s in run["steps"])
    assert [s["position"] for s in run["steps"]] == list(range(len(tools)))
    assert run["steps"][1]["label"] == "Read Mira's profile"
    assert run["steps"][1]["started_at"].endswith(("Z", "+00:00"))  # browsers mustn't read it as local time
    assert run["steps"][7]["result"].startswith('"Sandcastle Day", ')
    # Each tool step is streamed twice: once as it starts, once when it's done.
    started = [e for e in streamed if e[0] == "step" and e[1]["tool"] == "write_chapter"]
    assert [s["ok"] for _, s in started] == [None, True]

    adventure = run["adventure"]
    assert adventure["title"] == "The Great Beach Day"
    assert [c["status"] for c in adventure["chapters"]] == ["written", "planned", "planned"]
    assert adventure["chapters"][0]["safety_status"] == "passed"
    assert adventure["chapters"][1]["plot_cards"] == ["Beat 2a", "Beat 2b", "Beat 2c"]

    first = client.get(f"/api/stories/{adventure['chapters'][0]['story_id']}").json()
    assert first["title"] == "Sandcastle Day"
    assert first["adventure"] == {"id": adventure["id"], "title": "The Great Beach Day", "night": 1, "nights": 3}
    assert "night 1 of 3" in written[0][1]["content"]


def test_the_story_list_keeps_an_adventures_nights_together_in_order(client, monkeypatch, cast, written):
    checks(monkeypatch)
    client.post("/api/stories", json={"character_ids": [cast["Minnie"]]})
    run_agent(client, monkeypatch, plan_calls(cast))
    client.post("/api/stories", json={"character_ids": [cast["Tosia"]]})
    listed = [(s["title"], (s["adventure"] or {}).get("night")) for s in client.get("/api/stories").json()]
    assert listed == [
        ("A story with Tosia", None),
        ("Night 1", 1),
        ("Night 2", 2),
        ("Night 3", 3),
        ("A story with Minnie", None),
    ]


def test_a_failed_chapter_is_rewritten_once_before_it_is_saved(client, monkeypatch, cast, written):
    checks(monkeypatch, False, True)
    turns = plan_calls(cast) + [
        ("", [("write_chapter", {"night": 1})]),
        ("", [("save_story", {"night": 1})]),  # refused: not checked
        ("", [("safety_check", {"night": 1})]),  # fails
        ("", [("save_story", {"night": 1})]),  # refused: failed, not rewritten yet
        ("", [("write_chapter", {"night": 1})]),  # the rewrite
        ("", [("safety_check", {"night": 1})]),  # passes
        ("", [("save_story", {"night": 1})]),
        ("Done.", []),
    ]
    run_id, _, _ = run_agent(client, monkeypatch, turns)
    run = client.get(f"/api/agent-runs/{run_id}").json()
    steps = [s for s in run["steps"] if s["tool"] != "message"][4:]
    assert [(s["label"], s["ok"]) for s in steps] == [
        ("Write night 1", True),
        ("Save night 1", False),
        ("Safety check on night 1", False),
        ("Save night 1", False),
        ("Rewrite night 1", True),
        ("Safety check on night 1", True),
        ("Save night 1", True),
    ]
    assert steps[1]["result"] == "Check night 1 with safety_check before saving it."
    assert steps[3]["result"] == "Night 1 failed its check: rewrite it once with write_chapter first."
    assert run["status"] == "finished"
    assert run["adventure"]["chapters"][0]["safety_status"] == "rewritten"
    # The rewrite was asked to fix what the check found.
    assert "Too scary: make the waves gentle." in written[1][-1]["content"]


def test_a_chapter_that_fails_twice_is_saved_for_a_parent_to_read(client, monkeypatch, cast, written):
    checks(monkeypatch, False, False)
    turns = plan_calls(cast) + [
        ("", [("write_chapter", {"night": 1})]),
        ("", [("safety_check", {"night": 1})]),
        ("", [("write_chapter", {"night": 1})]),
        ("", [("safety_check", {"night": 1})]),
        ("", [("write_chapter", {"night": 1})]),  # refused: only one rewrite
        ("", [("save_story", {"night": 1})]),
    ]
    run_id, _, _ = run_agent(client, monkeypatch, turns)
    run = client.get(f"/api/agent-runs/{run_id}").json()
    refused = [s for s in run["steps"] if s["tool"] == "write_chapter"][-1]
    assert refused["ok"] is False
    assert run["status"] == "finished"
    assert run["adventure"]["chapters"][0]["safety_status"] == "needs_review"
    assert len(written) == 2


def test_plans_must_use_real_characters_and_the_ones_asked_for(client, monkeypatch, cast, written):
    bad = {"title": "A", "premise": "B", "nights": [{"title": "N", "character_ids": [999], "beats": ["a", "b"]}] * 3}
    no_bela = {
        "title": "A",
        "premise": "B",
        "nights": [{"title": "N", "character_ids": [cast["Minnie"]], "beats": ["a", "b"]}] * 3,
    }
    too_few = {**no_bela, "nights": no_bela["nights"][:2]}
    turns = [("", [("create_plot_cards", bad), ("create_plot_cards", no_bela), ("create_plot_cards", too_few)])]
    run_id, model, streamed = run_agent(client, monkeypatch, turns, character_ids=[cast["Diggles"]])

    assert model.tool_results() == [
        {"error": "Night 1: there are no characters with ids [999]."},
        {"error": "The parent asked for Diggles: put them in at least one night."},
        {"error": "Plan exactly 3 nights."},
    ]
    assert streamed[-1][1]["status"] == "failed"
    assert streamed[-1][1]["error"] == "Stopped before saving night 1."
    assert streamed[-1][1]["adventure"] is None


def test_only_tonights_night_is_written(client, monkeypatch, cast, written):
    turns = plan_calls(cast) + [("", [("write_chapter", {"night": 2})])]
    _, model, _ = run_agent(client, monkeypatch, turns)
    assert model.tool_results() == [{"error": "Only night 1 is written in this run."}]
    assert written == []


def test_a_run_stops_after_too_many_steps(client, monkeypatch, cast):
    turns = [("", [("get_child_profile", {})])] * 30
    _, model, streamed = run_agent(client, monkeypatch, turns)
    assert streamed[-1][1]["status"] == "failed"
    assert streamed[-1][1]["error"] == f"Stopped after {adventure_agent.MAX_TOOL_CALLS} steps without finishing."
    assert len(model.seen) == adventure_agent.MAX_TOOL_CALLS + 1


def test_unknown_tools_and_bad_arguments_are_reported_to_the_model(client, monkeypatch):
    turns = [("", [("delete_everything", {}), ("write_chapter", {"chapter": 1}), ("list_characters", {"_invalid": "{"})])]
    _, model, _ = run_agent(client, monkeypatch, turns)
    assert model.tool_results() == [
        {"error": "There is no tool called delete_everything."},
        {"error": "Wrong arguments for this tool."},
        {"error": "The arguments were not valid JSON."},
    ]


def test_the_theme_is_passed_as_a_topic(client, monkeypatch):
    _, model, _ = run_agent(client, monkeypatch, [], theme="the beach")
    goal = model.seen[0][1]["content"]
    assert "plan a 3-night adventure for Mira" in goal
    assert "<theme>the beach</theme>" in goal


def test_next_night_continues_the_adventure(client, monkeypatch, cast, written):
    checks(monkeypatch, True, True)
    plan = plan_calls(cast) + [
        ("", [("write_chapter", {"night": 1})]),
        ("", [("safety_check", {"night": 1})]),
        ("", [("save_story", {"night": 1})]),
    ]
    run_id, _, _ = run_agent(client, monkeypatch, plan)
    adventure_id = client.get(f"/api/agent-runs/{run_id}").json()["adventure"]["id"]

    model = ScriptedModel(
        [
            ("", [("get_previous_stories", {}), ("create_plot_cards", {"title": "X", "premise": "Y", "nights": []})]),
            ("", [("write_chapter", {"night": 2})]),
            ("", [("safety_check", {"night": 2})]),
            ("", [("save_story", {"night": 2})]),
        ]
    )
    monkeypatch.setattr(llm, "complete_with_tools", model)
    response = client.post(f"/api/adventures/{adventure_id}/next")
    assert response.status_code == 201
    assert response.json()["goal"] == 'Write night 2 of "The Great Beach Day"'
    streamed = events(client.get(f"/api/agent-runs/{response.json()['id']}/stream").text)

    assert streamed[-1][1]["status"] == "finished"
    first_tools = model.seen[1][-2:]
    assert json.loads(first_tools[0]["content"])["this_adventure"]["nights"][0]["written"] is True
    assert json.loads(first_tools[1]["content"]) == {"error": "This adventure is already planned."}
    chapter_prompt = written[-1][1]["content"]
    assert "night 2 of 3" in chapter_prompt
    assert 'Night 1, "Sandcastle Day"' in chapter_prompt
    assert "Beat 2a" in chapter_prompt
    chapters = client.get(f"/api/adventures/{adventure_id}").json()["chapters"]
    assert [c["status"] for c in chapters] == ["written", "written", "planned"]


def test_next_night_refuses_while_a_run_is_going_or_when_finished(client, monkeypatch, cast, written, engine):
    checks(monkeypatch)
    plan = plan_calls(cast, nights=2) + [
        ("", [("write_chapter", {"night": 1})]),
        ("", [("safety_check", {"night": 1})]),
        ("", [("save_story", {"night": 1})]),
    ]
    model = ScriptedModel(plan)
    monkeypatch.setattr(llm, "complete_with_tools", model)
    run = client.post("/api/adventures", json={"nights": 2}).json()
    client.get(f"/api/agent-runs/{run['id']}/stream")
    adventure_id = client.get(f"/api/agent-runs/{run['id']}").json()["adventure"]["id"]

    pending = client.post(f"/api/adventures/{adventure_id}/next")
    assert pending.status_code == 201
    assert client.post(f"/api/adventures/{adventure_id}/next").status_code == 409

    model.turns = [
        ("", [("write_chapter", {"night": 2})]),
        ("", [("safety_check", {"night": 2})]),
        ("", [("save_story", {"night": 2})]),
    ]
    client.get(f"/api/agent-runs/{pending.json()['id']}/stream")
    assert client.get(f"/api/adventures/{adventure_id}").json()["status"] == "finished"
    finished = client.post(f"/api/adventures/{adventure_id}/next")
    assert finished.status_code == 409
    assert finished.json()["detail"] == "Every night of this adventure has been written"


def test_a_run_streams_only_once(client, monkeypatch):
    run_id, _, _ = run_agent(client, monkeypatch, [])
    assert client.get(f"/api/agent-runs/{run_id}/stream").status_code == 409


def test_a_run_cut_off_mid_way_shows_as_stopped(client, engine):
    with Session(engine) as session:
        run = AgentRun(
            kind=AgentRunKind.plan,
            goal="Plan",
            status=AgentRunStatus.running,
            created_at=utc_now() - timedelta(minutes=10),
        )
        session.add(run)
        session.commit()
        run_id = run.id
    body = client.get(f"/api/agent-runs/{run_id}").json()
    assert body["status"] == "stopped"


def test_adventure_nights_are_not_written_as_single_stories(client, monkeypatch, cast, written):
    run_id, _, _ = run_agent(client, monkeypatch, plan_calls(cast))
    night = client.get(f"/api/agent-runs/{run_id}").json()["adventure"]["chapters"][0]["story_id"]
    response = client.get(f"/api/stories/{night}/stream")
    assert response.status_code == 409
    assert client.get(f"/api/stories/{night}").json()["plot_cards"] == ["Beat 1a", "Beat 1b", "Beat 1c"]


def test_each_run_counts_towards_the_daily_limit(client, monkeypatch):
    monkeypatch.setenv("MAX_STORIES_PER_DAY", "1")
    assert client.post("/api/adventures", json={"nights": 3}).status_code == 201
    assert client.post("/api/adventures", json={"nights": 3}).status_code == 429


def test_planned_nights_dont_count_towards_the_daily_limit(client, monkeypatch, cast, written, engine):
    run_agent(client, monkeypatch, plan_calls(cast, nights=5), nights=5)
    with Session(engine) as session:
        assert len(session.exec(select(Story)).all()) == 5
    monkeypatch.setenv("MAX_STORIES_PER_DAY", "2")
    assert client.post("/api/stories", json={"character_ids": [cast["Minnie"]]}).status_code == 201


@pytest.mark.parametrize(
    ("body", "status"),
    [({"nights": 9}, 422), ({"nights": 1}, 422), ({"theme": "x" * 201}, 422), ({"character_ids": [999]}, 404)],
)
def test_plan_request_is_checked(client, body, status):
    assert client.post("/api/adventures", json=body).status_code == status


def test_unknown_runs_and_adventures_are_404(client):
    assert client.get("/api/agent-runs/999").status_code == 404
    assert client.get("/api/agent-runs/999/stream").status_code == 404
    assert client.get("/api/adventures/999").status_code == 404
    assert client.post("/api/adventures/999/next").status_code == 404
    assert client.get("/api/adventures").json() == []
