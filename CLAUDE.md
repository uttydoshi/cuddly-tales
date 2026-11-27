# CLAUDE.md — Cuddly Tales

## What this is
A take-home assessment app (due in 3 days) for a Head of Engineering (AI) role.
"Cuddly Tales" generates short, gentle bedtime stories for young children (ages 2–6), starring
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
  The built Angular app is served by FastAPI, so the whole app deploys as a single service.
- Backend: Python, FastAPI, SQLModel. SQLite locally; hosted Postgres (Neon or Supabase free tier) in production.
  The only difference is `DATABASE_URL`.
- LLM access: LiteLLM SDK (model-agnostic; model name set in env config).
- Streaming: Server-Sent Events from FastAPI to Angular.
- Scheduling: APScheduler inside the FastAPI app, plus a "Run now" endpoint so reviewers can trigger it.
- Observability: Langfuse tracing on every LLM call, tagged with feature name and story id.
- Deploy: a single Render web service, auto-deployed from GitHub, on the custom domain `cuddly-tales.ukdoshi.com`
  (a CNAME record in Route 53 pointing to Render). Secrets in env vars only, never committed.
- Free hosting tiers may sleep when idle, so the scheduled job also has a "Run now" button for the demo.
- Future: move to AWS (App Runner) alongside ukdoshi.com.

## Domain model
- **ChildProfile**: name, age (2–6), favourite things. One per deployment for now; the hero of every story.
  Age drives story length, vocabulary and the scariness limit.
- **Character**: name, type (family | original | folklore | latte_monster | custom), description,
  personality traits, running gags / consistency rules, image (optional, latte monsters only).
- **Story**: title, characters (many-to-many), plot cards (ordered), status
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
  simple vocabulary, nothing frightening, a warm and calm ending suitable for sleep.

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
