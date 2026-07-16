# Automated Book Generation System

A modular **FastAPI** backend that generates book outlines and chapters using **OpenRouter** (OpenAI-compatible API), stores state in **Supabase**, and supports **human-in-the-loop** review gates at every stage.

Test interactively via **Swagger UI** at `/docs` or with Postman/curl.

## Features

- **Outline generation** from a title and optional author notes
- **Chapter generation** one at a time with **context chaining** (prior chapter summaries injected into each prompt)
- **Human-in-the-loop gating** via status fields on books and chapters
- **Final review gate** before downloadable compilation
- **Health check** with Supabase and OpenRouter connectivity status
- **Docker** support for local deployment
- **Project management** (create projects, manage API keys)
- **Template management** (create, list, update, delete templates)
- **Webhooks** for outline approval and chapter completion events

## Tech Stack

| Layer | Technology |
|--------|------------|
| API | FastAPI, Uvicorn |
| Database | Supabase (PostgreSQL + PostgREST) |
| LLM | OpenRouter via `openai` Python SDK |
| Config | Pydantic Settings |
| Authentication | JWT (access/refresh tokens) |
| API Keys | Project-based API keys with revocation/expiration |

## Project Structure

```
├── app/
│   ├── main.py              # FastAPI entry point, router registration
│   ├── models.py            # Pydantic schemas (BookResponse, ChapterResponse, StageStatus, BookPhase)
│   ├── modules/
│   │   ├── auth/            # Authentication (login, register, refresh)
│   │   ├── books/           # Book and chapter operations (CRUD, generation, human-in-the-loop)
│   │   ├── projects/        # Project and API key management
│   │   ├── templates/       # Template management
│   │   ├── webhooks/        # Outline approved and chapter completed webhooks
│   │   └── generation/      # Outline and chapter generation services
│   ├── core/
│   │   └── config.py        # Environment settings
│   └── services/
│       ├── ai_service.py    # LLM: outline, chapter, summarization
│       ├── db_service.py    # Supabase client wrappers
│       └── supabase_errors.py  # Error handling
├── sql/
│   ├── schema.sql           # Full database schema
│   ├── rls_policies.sql     # Row-level security for anon key
│   └── migration_*.sql      # Incremental migrations
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── contract-api.md          # Detailed API contract reference
└── .env.example
```

## Prerequisites

- Python 3.12+ (local run) or Docker
- [Supabase](https://supabase.com) project
- [OpenRouter](https://openrouter.ai) API key

## Setup

### 1. Supabase database

In the Supabase **SQL Editor**, run in order:

1. `sql/schema.sql` — creates `books` and `chapters` tables  
2. `sql/rls_policies.sql` — **required** if using the `anon` API key  

Confirm tables appear under **Table Editor**.

### 2. Environment variables

```bash
cp .env.example .env
```

Edit `.env`:

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Project URL from Supabase → Settings → API |
| `SUPABASE_KEY` | Prefer **service_role** secret for backend; or use `anon` + `rls_policies.sql` |
| `OPENAI_API_KEY` | OpenRouter key (`sk-or-v1-...`) |
| `OPENAI_BASE_URL` | `https://openrouter.ai/api/v1` |
| `OPENAI_MODEL` | e.g. `openai/gpt-4o-mini` |
| `REQUIRE_HUMAN_REVIEW` | `true` pauses after AI steps for human approval |

### 3. Run with Docker (recommended)

```bash
docker compose up --build -d
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs

### 4. Run locally (optional)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## API Documentation

For a complete, detailed reference of all endpoints, request/response formats, and error codes, see [`contract-api.md`](contract-api.md).

### Quick Overview

Base path: `/api/v1`

#### Authentication
- `POST /auth/login` – Obtain access and refresh tokens
- `POST /auth/register` – Register a new user
- `POST /auth/refresh` – Refresh access token

#### Books & Chapters
- `POST /books` – Create a new book and generate outline
- `GET /books` – List all books (newest first)
- `GET /books/{book_id}` – Get a specific book
- `PATCH /books/{book_id}/outline` – Update outline notes and status (human-in-the-loop)
- `PATCH /books/{book_id}/final-review` – Update final review status (required for compile)
- `POST /books/{book_id}/chapters/next` – Generate next chapter using prior summaries
- `GET /books/{book_id}/chapters` – List chapters for a book
- `PATCH /chapters/{chapter_id}` – Update chapter notes and status (human-in-the-loop)
- `POST /chapters/{chapter_id}/regenerate` – Regenerate chapter with notes
- `POST /books/{book_id}/chapters/{chapter_id}/moderate` – Moderate chapter content
- `GET /books/{book_id}/draft` – Export full book draft as JSON
- `GET /books/{book_id}/compile` – Download compiled book as `.txt` (requires final review cleared)

#### Export
- `GET /books/{book_id}/export/pdf` – Get URL for PDF export
- `GET /books/{book_id}/export/epub` – Get URL for EPUB export
- `GET /books/{book_id}/export/markdown` – Get URL for Markdown export
- `GET /books/{book_id}/export/html` – Get URL for HTML export

#### Projects
- `POST /projects/` – Create a new project
- `GET /projects/{proj_id}` – Get a project
- `PATCH /projects/{proj_id}` – Update project
- `DELETE /projects/{proj_id}` – Delete project
- `POST /projects/{proj_id}/keys` – Generate API key for
- `POST /projects/{proj_id}/keys` – Generate a new API key for the project
- `GET /projects/{proj_id}/keys` – List API keys for the project
- `PATCH /projects/{proj_id}/keys/{key_id}` – Revoke or update an API key
- `DELETE /projects/{proj_id}/keys/{key_id}` – Delete an API key

#### Templates
- `POST /templates/` – Create a new template
- `GET /templates/` – List templates (with optional filters)
- `GET /templates/{template_id}` – Get a specific template
- `PATCH /templates/{template_id}` – Update a template
- `DELETE /templates/{template_id}` – Delete a template

#### Webhooks
- `POST /webhooks/outline-approved` – Send outline approved notifications
- `POST /webhooks/chapter-completed` – Send chapter completed notifications

#### Health & Stats
- `GET /health` – Health check (Supabase, OpenRouter)
- `GET /stats` – Get analytics dashboard statistics

## End-to-end Test Flow

1. **Health** – `GET /api/v1/health` → both services `ok`
2. **Outline** – `POST /api/v1/generate-outline` with `title` and `notes`
3. **Approve outline** – `PATCH /api/v1/books/{id}/outline` → `"status": "approved"`
4. **Chapter stubs** – Insert rows in Supabase `chapters` (one per outline chapter) with `"status": "approved"`, or use `POST /books/{id}/chapters/next`
5. **Generate chapters** – `POST /api/v1/generate-chapter` with each `chapter_id`; PATCH to `approved` after review
6. **Final review** – `PATCH /api/v1/books/{id}/final-review` → `"status": "no_notes_needed"`
7. **Compile** – `GET /api/v1/books/{id}/compile` → downloads text file

## Status Gates (Human-in-the-Loop)

| Field | Values | Purpose |
|-------|--------|---------|
| `books.outline_status` | `draft`, `review`, `approved`, `rejected`, `no_notes_needed` | Outline approval |
| `chapters.status` | `draft`, `review`, `approved`, `revision_requested`, `no_notes_needed` | Chapter generation gate |
| `books.final_review_notes_status` | `no notes`, `notes pending`, `addressed` | Must be `no_notes_needed` for `/compile` |

`POST /generate-chapter` only runs when the chapter row is `approved` or `no_notes_needed`. Otherwise returns **409** – `Waiting for human review`.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Health: Supabase error / table missing | Run `sql/schema.sql` |
| 403 RLS on insert | Run `sql/rls_policies.sql` or use `service_role` key |
| 503 Cannot reach Supabase | Check `SUPABASE_URL`; restart Docker (`docker compose up --build -d`) |
| 403 on compile | `PATCH .../final-review` with `no_notes_needed` |
| OpenRouter auth errors | Verify `OPENAI_BASE_URL` and `OPENAI_MODEL` |

## Push to GitHub

```bash
git init -b main
git add .
git commit -m "Initial commit: automated book generation API"
git remote add origin https://github.com/YOUR_USERNAME/Automated-Book-Generation-System.git
git push -u origin main
```

Create an empty repository on GitHub first, then replace the remote URL.

## Push to Docker Hub

### 1. Log in (one time)

Create a **Personal Access Token** at [Docker Hub → Security](https://hub.docker.com/settings/security), then:

```bash
echo "YOUR_DOCKER_HUB_TOKEN" | docker login -u YOUR_USERNAME --password-stdin
```

If you see `pass not initialized`, remove the broken credential helper (one time):

```bash
python3 -c "import json, pathlib; p=pathlib.Path.home()/'.docker/config.json'; c=json.loads(p.read_text()); c.pop('credsStore',None); p.write_text(json.dumps(c,indent=2))"
```

Then run `docker login` again with the token command above.

### 2. Build and push

```bash
chmod +x docker-publish.sh
export DOCKERHUB_USER=your-dockerhub-username
./docker-publish.sh
```

Optional version tag:

```bash
IMAGE_TAG=v1.0.0 ./docker-publish.sh
```

This publishes `your-dockerhub-username/automated-book-generation-system:latest`.

### 3. Run the image from Docker Hub

```bash
docker pull your-dockerhub-username/automated-book-generation-system:latest
docker run -p 8000:8000 --env-file .env \
  your-dockerhub-username/automated-book-generation-system:latest
```

API: http://localhost:8000/docs

> **Note:** Do not bake `.env` into the image. Pass secrets at runtime with `--env-file` or `-e` flags.

### Manual commands (without script)

```bash
export DOCKERHUB_USER=your-dockerhub-username
docker build -t $DOCKERHUB_USER/automated-book-generation-system:latest .
docker push $DOCKERHUB_USER/automated-book-generation-system:latest
```