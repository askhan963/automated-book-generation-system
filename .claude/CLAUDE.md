# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Run locally with hot reload
./run.sh
# or: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run with Docker
docker compose up --build -d

# API available at http://localhost:8000
# Swagger UI at http://localhost:8000/docs
```

## Architecture

This is a **FastAPI** backend for automated book generation with **human-in-the-loop** review gates:

```
app/
├── main.py           # FastAPI entry point, router registration
├── models.py         # Pydantic schemas (BookResponse, ChapterResponse, StageStatus, BookPhase)
├── api/
│   ├── routes.py     # CRUD endpoints for books, chapters, compile, health
│   └── generation.py # POST /generate-outline, POST /generate-chapter, POST /books/{id}/chapters/next
└── services/
    ├── ai_service.py # OpenRouter/LLM: generate_outline(), generate_chapter(), summarize_chapter()
    ├── db_service.py # Supabase client wrappers for books/chapters CRUD
    └── supabase_errors.py  # Error handling
```

**Data flow**: Requests → routes → db_service (fetch/save) ↔ ai_service (LLM calls) → db_service (save results) → responses.

**Human-in-the-loop gates**: Chapter generation requires `status: approved` or `no_notes_needed` on the chapter row. Compile requires `final_review_notes_status: no_notes_needed` on the book.

## Database Schema

See `sql/schema.sql` for tables:
- `books`: id, title, outline (JSON), outline_status, final_review_notes_status, phase
- `chapters`: id, book_id, chapter_number, title, content, summary, status

Run `sql/rls_policies.sql` if using Supabase anon key instead of service_role.