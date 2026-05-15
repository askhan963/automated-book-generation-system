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

## Tech Stack

| Layer | Technology |
|--------|------------|
| API | FastAPI, Uvicorn |
| Database | Supabase (PostgreSQL + PostgREST) |
| LLM | OpenRouter via `openai` Python SDK |
| Config | Pydantic Settings |

## Project Structure

```
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── models.py            # Pydantic schemas & enums
│   ├── api/
│   │   ├── routes.py        # Books, chapters, compile, health
│   │   └── generation.py    # generate-outline, generate-chapter
│   ├── core/
│   │   └── config.py        # Environment settings
│   └── services/
│       ├── ai_service.py    # LLM: outline, chapter, summarize
│       ├── db_service.py    # Supabase CRUD
│       └── supabase_errors.py
├── sql/
│   ├── schema.sql           # Full database schema
│   ├── rls_policies.sql     # Row-level security for anon key
│   └── migration_*.sql      # Incremental migrations
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
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
2. `sql/migration_add_outline_review.sql` — if upgrading an older DB  
3. `sql/migration_add_final_review_status.sql` — if upgrading an older DB  
4. `sql/rls_policies.sql` — **required** if using the `anon` API key  

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

## API Endpoints

Base path: `/api/v1`

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | App, Supabase, and OpenRouter status |

### Generation

| Method | Path | Description |
|--------|------|-------------|
| POST | `/generate-outline` | Generate outline; save book with `outline_review` |
| POST | `/generate-chapter` | Generate chapter + summary (requires approved chapter row) |

### Books & chapters

| Method | Path | Description |
|--------|------|-------------|
| POST | `/books` | Create book + outline (alternative flow) |
| GET | `/books/{book_id}` | Get book |
| PATCH | `/books/{book_id}/outline` | Approve / add notes on outline |
| PATCH | `/books/{book_id}/final-review` | Clear final review for compile |
| POST | `/books/{book_id}/chapters/next` | Create + generate next chapter |
| GET | `/books/{book_id}/chapters` | List chapters |
| PATCH | `/chapters/{chapter_id}` | Approve / add notes on chapter |
| POST | `/chapters/{chapter_id}/regenerate` | Regenerate chapter with notes |
| GET | `/books/{book_id}/draft` | JSON preview of full draft |
| GET | `/books/{book_id}/compile` | Download `.txt` (requires final review cleared) |

Interactive docs: **http://localhost:8000/docs**

## End-to-end test flow

1. **Health** — `GET /api/v1/health` → both services `ok`
2. **Outline** — `POST /api/v1/generate-outline` with `title` and `notes`
3. **Approve outline** — `PATCH /api/v1/books/{id}/outline` → `"status": "approved"`
4. **Chapter stubs** — Insert rows in Supabase `chapters` (one per outline chapter) with `"status": "approved"`, or use `POST /books/{id}/chapters/next`
5. **Generate chapters** — `POST /api/v1/generate-chapter` with each `chapter_id`; PATCH to `approved` after review
6. **Final review** — `PATCH /api/v1/books/{id}/final-review` → `"status": "no_notes_needed"`
7. **Compile** — `GET /api/v1/books/{id}/compile` → downloads text file

### Example: generate outline

```bash
curl -X POST http://localhost:8000/api/v1/generate-outline \
  -H "Content-Type: application/json" \
  -d '{"title": "The Last Lighthouse", "notes": "Mystery on a remote island."}'
```

### Example: clear final review and compile

```bash
curl -X PATCH "http://localhost:8000/api/v1/books/{BOOK_ID}/final-review" \
  -H "Content-Type: application/json" \
  -d '{"status": "no_notes_needed", "human_notes": "Ready to publish."}'

curl -O -J "http://localhost:8000/api/v1/books/{BOOK_ID}/compile"
```

## Status gates (human-in-the-loop)

| Field | Values | Purpose |
|-------|--------|---------|
| `books.outline_status` | `outline_review`, `pending_review`, `approved`, `no_notes_needed`, … | Outline approval |
| `chapters.status` | `pending_review`, `approved`, `no_notes_needed`, … | Chapter generation gate |
| `books.final_review_notes_status` | Must be `no_notes_needed` for `/compile` | Final publish gate |

`POST /generate-chapter` only runs when the chapter row is `approved` or `no_notes_needed`. Otherwise it returns **409** — `Waiting for human review`.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Health: Supabase error / table missing | Run `sql/schema.sql` |
| 403 RLS on insert | Run `sql/rls_policies.sql` or use **service_role** key |
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

