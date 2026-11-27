# CLAUDE.md — Cuddly Tales

## What this is
A take-home assessment app (due in 3 days) for a Head of Engineering (AI) role.
"Cuddly Tales" generates short, gentle stories for young children (ages 2–6), for any time of day or
as a calm bedtime story, starring
the child as the hero, their family and pets, original characters, public-domain folklore, and
"latte monsters" created from photos of latte art. Any family can use it: a parent sets up
the child's profile (name, age, favourite things) and their own characters. The seed data is
a demo family (Mira, aged 3, and her poodles Minnie and Maverick). AI does real work here: it generates, classifies,
checks, decides and acts. It is not a chatbot bolted onto a form.

## Assessment requirements (must cover at least 3; we are aiming for all 5)
1. **CRUD**: characters and stories can be created, viewed, edited and deleted, and are saved.
2. **In-app analytics**: a dashboard with at least 2 charts/KPIs computed from real app data.
3. **Drag and drop**: storyboard plot cards that can be reordered (order is saved), and/or stories moved across a board.
4. **Streaming and scheduled workloads**: story text streams word by word (SSE); a scheduled job prepares tonight's chapter.
5. **AI agent**: takes a goal ("Plan a 5-night adventure"), uses tools, and finishes a multi-step task, with every step visible to the user.

## Stack
- Frontend: Angular (standalone components), Angular CDK for drag and drop, Chart.js (ng2-charts) for the dashboard.
  In production it is served from S3 through CloudFront. Locally FastAPI can also serve the build (one process).
- Backend: Python, FastAPI, SQLModel, Alembic migrations (run at startup). SQLite locally; Neon Postgres (free tier,
  AWS us-east-1) in production. The only difference is `DATABASE_URL`.
- LLM access: LiteLLM SDK (model-agnostic; model name set in env config).
- Streaming: Server-Sent Events from FastAPI to Angular.
- Scheduling: EventBridge Scheduler (18:30 Australia/Melbourne) invokes the API on Lambda, plus a "Run now" endpoint
  so reviewers can trigger it.
- Observability: Langfuse tracing on every LLM call, tagged with feature name and story id.
- Deploy: AWS, defined with the AWS CDK in `infra/` (same patterns as ukdoshi-site and ukdoshi-lab, same account):
  FastAPI on Lambda via the Lambda Web Adapter behind a streaming Function URL, CloudFront in front of S3 and the API,
  on `cuddly-tales.ukdoshi.com` (records in the existing Route 53 zone, made by the CDK). GitHub Actions tests every
  PR and deploys `main` (OIDC, no stored keys). One live copy; staging can be added later.
- Secrets (Claude key, database URL) live in AWS Secrets Manager, set with `scripts/`; locally in `.env`. Never committed.
- The site is public with no sign-in, so new stories are capped (`MAX_STORIES_PER_DAY`, default 30) and the Claude
  key has its own spend limit.

## Domain model
- **ChildProfile**: name, age (2–6), favourite things. One per deployment for now; the hero of every story.
  Age drives story length, vocabulary and the scariness limit.
- **Character**: name, type (family | original | folklore | latte_monster | custom), description,
  personality traits, running gags / consistency rules, image (optional, latte monsters only).
- **Story**: title, characters (many-to-many), plot cards (ordered), bedtime (yes/no), status
  (idea | planned | written | read), text, reading time, safety check result, created/read dates.
- **PlotCard**: story id, position, short beat text.
- **AgentRun**: goal, status, ordered steps (tool name, input summary, output summary, timestamps).

## Seed cast (demo family; use exactly these in seed data, screenshots, demo and README)
- **Mira**: the demo child profile, a curious 3-year-old girl. (A made-up name; never use real family names other than the dogs.)
- **Minnie**: toy poodle, obsessed with her ball. Ignores everything else, even dragons.
  Rule: chases the ball at least once per story; everyone shouts "Minnie, NOT NOW!"; the ball accidentally leads to the clue.
- **Maverick**: toy poodle, extremely lazy couch king. Moves only for food, water and belly rubs.
  Rule: stays on the couch unless food is involved; his licks make everything better (including grumpy wolves).
- **Tosia**: a tidy, cosy cat who loves routines (bath time, getting dressed); teaches one simple Polish word per story.
- **Diggles**: a cheeky wombat who digs holes everywhere (often in Tosia's garden), steals socks, fiercely loyal to Mira.
- **Folklore (public domain)**: Baba Yaga (silly, not scary), Red Riding Hood, the Gingerbread Man, the Big Bad Wolf.
- **Panchatantra animals (public domain)**: the clever monkey and the crocodile.
- Setting flavour: an Australian backyard and bush, with an Indian and Polish family heritage.

## Content rules (non-negotiable)
- No copyrighted or trademarked characters anywhere in the repo: seed data, prompts, tests, screenshots or docs.
  Parents may add custom characters at runtime; those are user data and never committed.
- No real children's names or family photos in the repo.
- Stories match the child's age (default 3): a 3–5 minute read (roughly 300–600 words for age 3),
  simple vocabulary, nothing frightening, and a warm, happy ending. A bedtime story (the parent's choice per
  story) ends calm and ready for sleep, and reads in night mode.

## AI features
1. **Story generation (streaming)**: build the prompt from the selected characters, their rules and the ordered plot cards; stream the text.
2. **Safety and age check (guardrail)**: after generation, an LLM-as-judge plus simple rules score scariness (1–5),
   reading level, length and character-rule adherence. If a check fails, the story is rewritten once, then flagged for parent review.
3. **Latte monster creator (vision)**: upload a latte art photo; the model describes the shape and invents a
   character (name, look, personality, one running gag), which a parent approves before it is saved.
4. **Adventure agent**: goal "Plan an N-night adventure for <child name>". Tools:
   `get_child_profile`, `list_characters`, `get_previous_stories`, `create_plot_cards`, `write_chapter`, `safety_check`, `save_story`.
   Each step is persisted to AgentRun and streamed to the UI as it happens.
5. **Scheduled job**: daily at 18:30 (Australia/Melbourne), prepare tonight's next chapter if an adventure is in progress.

## Evals
- `evals/` contains about 10 sample story requests with expectations: scariness ≤ 2, word count range,
  required character rules present (Minnie chases the ball; Maverick stays on the couch), no banned characters.
- `python -m evals.run` prints a pass/fail table. Keep it runnable locally in under 2 minutes.

## How we work (for Claude Code)
- Build the **cocoon first**: one happy path end to end (pick characters → generate → stream → save → view)
  before adding any other feature.
- Plan before coding, and confirm the plan with me before large changes.
- Small, focused commits with clear messages (reviewers will read the git history).
- Keep it simple: no auth (one family per deployment), SQLite locally, minimal styling until features work.
  Multiple families with sign-in is a README "next step", not in scope.
- Every new endpoint gets at least one basic test (pytest).
- Never commit secrets; use `.env` (git-ignored) and document variables in `.env.example`.

## Things to know (learned while building)
- **Branches and deploys**: work on a feature branch and open a PR. GitHub Actions tests every PR; merging to `main`
  deploys to the live site. Check the deploy run (and Lambda's logs) after each merge; tests passing is not enough.
- **iCloud**: the repo lives in `~/Documents/code.nosync` (with a `~/Documents/code` link) so iCloud doesn't sync it.
  iCloud once made stale `name 2` copies of files during branch switches, and some got committed. If ` 2` files
  appear, delete them; never commit them.
- **Lambda limits shape the backend**:
  - The package must stay under 250 MB unzipped (about 213 MB now, mostly LiteLLM). `infra/stacks/bundle.py` drops
    LiteLLM's unused proxy dashboard and stops the build above 235 MB. Check the size before adding a dependency.
  - The app must start within 10 seconds. Keep heavy imports lazy: LiteLLM loads in `llm.load_litellm()`, and a test
    fails if `app.main` imports it. Bytecode ships as unchecked-hash `.pyc` because the CDK fixes file timestamps.
  - Bundling runs as its own process, never inside the CDK's: forking there breaks the CDK ("unexpected EOF").
  - CloudFront waits at most 60 seconds between bytes, so long streams send keep-alives (`with_keepalive`).
- **Database**: every model change needs an Alembic migration (`alembic revision --autogenerate`, from `backend/`);
  `tests/test_migrations.py` fails otherwise. Migrations run at app start under a Postgres advisory lock.
- **LLM calls**: current Claude models reject `temperature` and other sampling parameters, so never send them. Thinking
  effort is `LLM_REASONING_EFFORT` (LiteLLM maps `reasoning_effort` to Anthropic's effort setting).
- **Claude key**: it lives in its own Anthropic workspace ("Cuddly Tales") with a monthly spend limit. Keys can't move
  between workspaces, and the default workspace can't have a spend limit.
- **AWS**: SSO profile `ukdoshi`, region `us-east-1`. Secrets are set only with `scripts/claude-key.sh` and
  `scripts/database-url.sh`; never paste a secret into chat or a file. The deploy role trusts only this repo's `main`.
- **Local-only changes**: don't commit the Angular CLI's `cli.analytics` id in `frontend/angular.json`.
- **Diagrams**: `docs/architecture.html` is the source; `docs/*.svg` are generated from it for the README. Keep them in
  step with what's built, and redraw them before submission.

## Build order
- Day 1: repo setup → cocoon happy path → CRUD for characters and stories → seed data → first deploy.
- Day 2: streaming polish → safety check guardrail → adventure agent with visible steps → Langfuse tracing → latte monster creator.
- Day 3: storyboard drag and drop → dashboard → scheduled job + "Run now" → evals → README and polish.
- If short on time, cut in this order: Polish-only "for Babcia" mode, audio, then the latte creator's extras. Never cut the README or evals.

## Dashboard KPIs (ideas)
- Stories read this week; average reading time.
- Character appearances (bar chart); most-loved character.
- Polish words learned (count); latte monsters adopted.
- Safety check pass rate on the first attempt.

## README must include
- What it is and why (one paragraph), plus a screenshot or GIF.
- Architecture diagram (frontend, API, LLM via LiteLLM, SQLite, scheduler, Langfuse).
- How each of the 5 required features is met.
- Responsible AI: guardrails, content rights, child privacy, a parent always in control.
- How I used AI to build it (Claude Code workflow, this CLAUDE.md, what I reviewed and changed by hand).
- How to run locally, run evals, and the deployed link.
- What I'd do next.
