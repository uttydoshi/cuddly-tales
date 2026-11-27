# Cuddly Tales

Gentle bedtime stories for young children (ages 2–6), with the child as the hero alongside their
family, pets, original characters and public-domain folklore. A parent picks tonight's cast, and the
story is written by an LLM and streamed to the screen word by word, ready to read aloud.

> Work in progress. This README grows with each feature.

## Architecture

![Architecture: the Angular app talks to one FastAPI service over JSON and Server-Sent Events; FastAPI stores data in SQLite through SQLModel and calls the LLM through LiteLLM](docs/architecture.svg)

One FastAPI service serves both the built Angular app and the API, so the app deploys as a single
unit. On the streaming path (amber), the LLM sends token chunks through LiteLLM, the story service
regroups them into whole words, and Server-Sent Events carry each word to the browser. Dashed parts
come later.

![Sequence: load the cast, create a planned story, stream it word by word, save the full text once at the end](docs/story-flow.svg)

The story row is created before any text arrives, so the stream has an id to save into. The full
text is saved once, when the model finishes. If generation fails, the browser gets an `error` event
and the story stays `planned`, so nothing half-written is kept.

A version with the scope of each slice is in [docs/architecture.html](docs/architecture.html).

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

### Run it as one service

In production FastAPI also serves the built Angular app:

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

## Configuration

All settings are environment variables, documented in [.env.example](.env.example).

| Variable | What it does |
| --- | --- |
| `LLM_MODEL` | Model name in LiteLLM format, e.g. `anthropic/claude-opus-5-5` |
| `ANTHROPIC_API_KEY` | API key for the model's provider |
| `DATABASE_URL` | SQLite locally; a Postgres URL in production |
