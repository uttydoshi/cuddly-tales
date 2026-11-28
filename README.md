# Cuddly Tales

Gentle stories for young children (ages 2–6), with the child as the hero alongside their family,
pets, original characters and public-domain folklore. A parent picks the cast and whether it's for
any time of day or bedtime, and the story is written by an LLM and streamed to the screen word by
word, ready to read aloud.

**Live: https://cuddly-tales.ukdoshi.com** (public; new stories are capped at 30 a day)

<p>
  <img src="docs/screenshots/pick-the-cast.png" width="200" alt="Picking the cast: 'Dear Mira, who's in Mira's story?', Anytime or Bedtime, Minnie and Diggles chosen, and a 'Write the story with 2 friends' button">
  <img src="docs/screenshots/story-streaming.png" width="200" alt="The story arriving word by word in night mode, with 'Still writing · 32 words so far'">
  <img src="docs/screenshots/reading-night-mode.png" width="200" alt="Reading the finished story in night mode, with the Polish word gwiazda in italics">
  <img src="docs/screenshots/your-stories.png" width="200" alt="Your stories: filter chips and story cards marked Unread or Read">
</p>

Designed for a parent's phone, in the style of [ukdoshi.com](https://ukdoshi.com): pick the cast,
watch the story arrive, then read it aloud in large type. Bedtime stories end calm and sleepy and open
in night mode; the whole site has a light and a dark theme.

> Built for a take-home assessment over three days. Day 1 is done; this README grows with each
> feature, and the table below shows what's in place and what's next.

## What it does

The assessment asks for at least three of five capabilities; Cuddly Tales aims for all five.

| Requirement | Status | How it's met |
| --- | --- | --- |
| **1. CRUD** | Done | Characters and stories can be created, viewed, edited and deleted, and are saved in Postgres. Stories can be marked read, and hearted to keep them under Favourites. The child's profile (name, age, favourite things) can be edited too; a new name is also changed in every story and character that used the old one. Deleting a character keeps the stories it was in. |
| **2. In-app analytics** | Day 3 | A dashboard with charts from real app data (stories read, character appearances, Polish words learned). |
| **3. Drag and drop** | Day 3 | A storyboard of plot cards that can be reordered, with the order saved. |
| **4. Streaming and scheduled work** | Streaming done; schedule Day 3 | Stories stream word by word over Server-Sent Events, live through CloudFront and Lambda. An EventBridge job at 18:30 (Melbourne) will prepare tonight's chapter, with a "Run now" button. |
| **5. AI agent** | Done | "Plan a 5-night adventure for Mira": the model works through the goal with 7 tools, choosing each next step; every step is saved and streamed live. See [The adventure agent](#the-adventure-agent). |

The demo family is Mira (3) and her cast: two toy poodles, Minnie and Maverick, Tosia the cat,
Diggles the wombat, and characters from public-domain folklore and the Panchatantra. Each character
has running jokes the story always follows, like Minnie chasing her ball while everyone shouts
"Minnie, NOT NOW!".

## The safety and age check

Every new story is checked before it's saved, as soon as it finishes streaming:

1. **Plain rules** (code, always the same answer): the length suits the child's age (about 300–600
   words at 3), there's a title, and none of a short list of frightening words appears.
2. **An LLM judge** (the same model, asked for a structured JSON verdict): scariness from 1 to 5
   (a story passes at 2 or below), whether the reading level suits the child's age, whether every
   character keeps their running-joke rules, whether everyone stays who they are (a cat isn't turned
   into a grandma), whether the ending is right (calm and sleepy for bedtime), and whether the story
   is new: not a repeat of, or too similar to, any of the family's last 30 stories. Any problems come
   back as short sentences a parent can read, with a one-sentence summary of what happens.

**Every story is new.** Before writing, the prompt lists the stories told so far (title and that
summary) and asks for a different main problem; the code also picks a kind of plot at random (a
surprise to prepare, building something, a visit somewhere new…), so the model doesn't keep falling
back on "something is lost". Running jokes stay small moments, never the whole plot. The check then
enforces it: a story too similar to an earlier one fails and is rewritten.

If the story fails, it's **rewritten once**, with the problems as feedback, and the rewrite streams
in place of the first version. If that fails too (or the check itself can't run), the story is
saved but marked **"Read first"**: the reading page lists what the check found, and a parent can
approve it, edit it or delete it. A story is never treated as safe without a check.

Each story keeps the full report (scores and problems for every version), so the dashboard can show
how often stories pass first time. One trade-off: the first version streams before it's checked,
because holding it back would remove the word-by-word streaming. The prompt sets the same limits,
the check runs within seconds of the end, and a failed story is replaced.

Tests never call the real model: a test fixture makes any unfaked model call fail.

## The adventure agent

A parent asks for an adventure (3 to 7 nights, optionally with characters who must be in it and a
theme). The agent gets the goal "Plan a 5-night adventure for Mira, then write, check and save
night 1" and seven tools:

| Tool | What it does |
|---|---|
| `get_child_profile`, `list_characters`, `get_previous_stories` | Read the child, the cast and the stories already told |
| `create_plot_cards` | Save the plan: a title, a premise, and each night's title, characters and plot cards |
| `write_chapter` | Write a night from its plot cards (the story prompt, plus the nights so far); called again after a failed check, it rewrites it |
| `safety_check` | The same safety and age check as every story |
| `save_story` | Save the checked chapter |

It's a real loop: the model chooses which tool to call next (LiteLLM tool calling), the code runs
it and returns the result, until the model says it's done. A typical run takes about 40 seconds and
10 tool calls. Before each call the model says in one sentence what it's doing; that sentence and
each tool's result are saved as steps and streamed to the parent's screen as they happen: a
live timeline with the tool names, timings, and what went in and out of each tool, then the plan,
night by night, with its plot cards. Each night shows in the stories list as "Night 2 of 5".

**The rules live in the tools, not only the prompt**, so a confused model can't break them: only
characters that exist, every character the parent asked for, exactly the nights asked for, 2 to 6
plot cards a night; only tonight's night is written in a run; nothing is saved before its check; a
chapter that fails is rewritten (once) before it's saved, then saved as "Read first" if it still
fails. A refused call is reported back to the model, which can correct itself. A run is capped at
25 tool calls and 4 minutes (Lambda stops a request at 5), and the parent's theme is passed as a
topic only. Planned nights don't count towards the daily story cap; each run does.

**One night per run.** The plan run writes night 1; each later night is its own run, started by
the evening scheduled job or a parent's "Write the next night now". Writing every night in one go
would take several minutes, close to Lambda's limit, and each night still needs its own check.

## Tracing with Langfuse

Every model call is traced in [Langfuse](https://langfuse.com), through LiteLLM's Langfuse
integration, so any story or agent run can be looked into afterwards: what the model was asked,
what it said, tokens, cost and time.

| Trace | Steps inside it |
|---|---|
| `story`: one per story written | `write`, `safety-check`, and `rewrite` + `safety-check` if it failed |
| `adventure-agent`: one per agent run | `agent-turn-1`, `agent-turn-2`… (each choice of tool), `write-chapter`, `safety-check`, and `rewrite-chapter` if it failed |

Traces are tagged with the feature and where the app ran (`live` or `local`), carry the story or
run id, and an adventure's runs share a Langfuse session, so all its nights can be followed
together. All model calls go through `backend/app/services/llm.py`, which is the only code that
knows about tracing.

On Lambda the process is frozen as soon as a response ends, so each story stream and agent run
sends its traces before it finishes (`tracing.flush()`), instead of leaving them queued.

**What's sent:** prompts include the child's first name, age and favourite things, and replies are
the stories. They go to a private Langfuse project (US region) that only the owner can see,
because that's what makes a failed safety check debuggable. `LANGFUSE_LOG_CONTENT=false` sends
only timings, tokens and cost. Without Langfuse keys, nothing is sent at all (and tests never send
anything).

## Architecture

![Architecture: the Angular app on a phone talks to CloudFront at cuddly-tales.ukdoshi.com, which serves the app from S3 and sends /api requests to FastAPI on AWS Lambda through a streaming Function URL; the Lambda reads secrets from Secrets Manager, calls the Anthropic API through LiteLLM and stores data in Neon Postgres; GitHub Actions deploys it with the CDK](docs/architecture.svg)

Live, the Angular app is served from S3 through CloudFront, and `/api/*` goes to FastAPI on AWS
Lambda through a streaming Function URL (see [Deployment](#deployment)). Locally, one FastAPI process
can serve both. On the streaming path (amber), the LLM sends token chunks through LiteLLM, the story service
regroups them into whole words, and Server-Sent Events carry each word to the browser. Dashed parts
come later.

![Sequence: load the cast, create a planned story, stream it word by word, save the full text once at the end](docs/story-flow.svg)

The story row is created before any text arrives, so the stream has an id to save into. The full
text is saved once, when the model finishes and the [safety check](#the-safety-and-age-check) has run. If generation fails, the browser gets an `error` event
and the story stays `planned`, so nothing half-written is kept.

A version with captions and progress so far is in [docs/architecture.html](docs/architecture.html).

## Run it locally

You need Python 3.13 and Node.js with npm. The Angular CLI is installed with the frontend packages.

```bash
# 1. Settings: copy the example and add your LLM API key
cp .env.example .env

# 2. Backend (FastAPI on http://localhost:8000)
cd backend
python3.13 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload

# 3. Frontend (Angular on http://localhost:4200, forwards /api to the backend)
cd frontend
npm install
npm start
```

Open http://localhost:4200. On first start the database (`backend/cuddly_tales.db`) is created
and seeded with the demo family: Mira (3) and her cast.

### Run it as one process

FastAPI can also serve the built Angular app, the way a single server would:

```bash
cd frontend && npm run build
cd ../backend && .venv/bin/uvicorn app.main:app
```

Then open http://localhost:8000.

## Tests

```bash
cd backend && .venv/bin/pytest        # API tests, with the LLM faked (no API key needed)
cd frontend && npx ng test --watch=false
```

GitHub Actions runs both on every pull request, and again before every deploy.

### Changing the database

Tables are managed with [Alembic](https://alembic.sqlalchemy.org). The app runs any new migrations
when it starts, locally and on Lambda. After changing a model in `backend/app/models.py`, add a
migration and check it in:

```bash
cd backend
.venv/bin/alembic revision --autogenerate -m "add plot cards"   # writes app/migrations/versions/...
```

Read the generated file before committing. A test (`tests/test_migrations.py`) fails if the models
and the migrations ever disagree.

## Configuration

All settings are environment variables, documented in [.env.example](.env.example).

| Variable | What it does |
| --- | --- |
| `LLM_MODEL` | Model name in LiteLLM format, e.g. `anthropic/claude-opus-5-5` |
| `ANTHROPIC_API_KEY` | API key for the model's provider |
| `LLM_REASONING_EFFORT` | How long the model thinks before writing (`low` starts the story sooner) |
| `MAX_STORIES_PER_DAY` | New stories allowed in any 24 hours across the site (default 30; 0 = no limit) |
| `DATABASE_URL` | SQLite locally; a Postgres URL in production |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | Langfuse project keys and region; tracing is off without them |
| `LANGFUSE_LOG_CONTENT` | `false` sends only timings, tokens and cost to Langfuse, not prompts or stories |

## Deployment

Live at **https://cuddly-tales.ukdoshi.com**, on AWS, in the same account and with the same
patterns as [ukdoshi.com](https://github.com/uttydoshi/ukdoshi-site) and
[lab.ukdoshi.com](https://github.com/uttydoshi/ukdoshi-lab). Everything is defined with the AWS CDK
in [`infra/`](infra).

| | |
| --- | --- |
| **Frontend** | Angular, in a private S3 bucket served through CloudFront |
| **API** | FastAPI on AWS Lambda (Python 3.13, arm64), run by the [Lambda Web Adapter](https://github.com/awslabs/aws-lambda-web-adapter) behind a streaming Function URL, so stories stream word by word. CloudFront adds a secret header and the API refuses requests without it. |
| **Database** | Neon Postgres (us-east-1), with Alembic migrations run when the API starts |
| **Secrets** | The Claude key and database URL in AWS Secrets Manager, set with `scripts/` |
| **DNS and HTTPS** | `cuddly-tales.ukdoshi.com` in the existing Route 53 zone, with an ACM certificate, both made by the CDK |
| **CI/CD** | GitHub Actions: tests on every pull request; on `main`, tests, build and `cdk deploy`, logging in to AWS with OIDC |
| **Cost guards** | No sign-in, so new stories are capped at 30 a day, and the Claude key has its own spend limit |

There is one live copy. A staging copy would be one more `Stage` in
[`infra/stacks/stage.py`](infra/stacks/stage.py) and a branch in the workflow.

### One-time setup (owner)

These need AWS access to the account (an SSO profile called `ukdoshi`). The account already has
the CDK bootstrap, the `ukdoshi.com` zone and GitHub's sign-in provider from ukdoshi-site.

```bash
aws sso login --profile ukdoshi
export AWS_PROFILE=ukdoshi

scripts/claude-key.sh      # paste a Claude key made just for Cuddly Tales
scripts/database-url.sh    # paste Neon's pooled connection URL
scripts/langfuse-keys.sh   # optional: paste the Langfuse project's keys to turn on tracing

cd infra
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
cdk deploy CuddlyTalesGithubDeploy    # the role GitHub Actions deploys with
```

After that, merging to `main` deploys. Running a script again replaces that secret and restarts
the API.
