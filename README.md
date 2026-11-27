# Cuddly Tales

Gentle bedtime stories for young children (ages 2–6), with the child as the hero alongside their
family, pets, original characters and public-domain folklore. A parent picks tonight's cast, and the
story is written by an LLM and streamed to the screen word by word, ready to read aloud.

> Work in progress. This README grows with each feature.

## Architecture

![Architecture: the Angular app talks to one FastAPI service over JSON and Server-Sent Events; FastAPI stores data in SQLite through SQLModel and calls the LLM through LiteLLM](docs/architecture.svg)

Live, the Angular app is served from S3 through CloudFront, and `/api/*` goes to FastAPI on AWS
Lambda through a streaming Function URL (see [Deployment](#deployment)). Locally, one FastAPI process
can serve both. On the streaming path (amber), the LLM sends token chunks through LiteLLM, the story service
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

## Configuration

All settings are environment variables, documented in [.env.example](.env.example).

| Variable | What it does |
| --- | --- |
| `LLM_MODEL` | Model name in LiteLLM format, e.g. `anthropic/claude-opus-5-5` |
| `ANTHROPIC_API_KEY` | API key for the model's provider |
| `LLM_REASONING_EFFORT` | How long the model thinks before writing (`low` starts the story sooner) |
| `MAX_STORIES_PER_DAY` | New stories allowed in any 24 hours across the site (default 30; 0 = no limit) |
| `DATABASE_URL` | SQLite locally; a Postgres URL in production |

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

cd infra
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
cdk deploy CuddlyTalesGithubDeploy    # the role GitHub Actions deploys with
```

After that, merging to `main` deploys. Running a script again replaces that secret and restarts
the API.
