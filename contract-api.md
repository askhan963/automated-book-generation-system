# API Contract Reference
Last updated: 2026-07-18

This document reflects the implemented FastAPI routes. The generated contract at
`/openapi.json` and interactive documentation at `/docs` are authoritative.

## Conventions

- Base URL in Docker Compose: `http://localhost:8001`
- Protected routes use `Authorization: Bearer <access_token>`.
- Project routes also accept `x-api-key: <key>` where noted.
- Responses are returned directly. There is no `{ "data": ... }` envelope.
- Validation failures use FastAPI's `422` response.
- Other API errors generally use `{ "detail": string }`.
- UUIDs and datetimes are JSON strings; datetimes use ISO 8601.
- There is currently no refresh-token endpoint.

### Shared enums

`StageStatus`:
`pending_notes | pending_review | outline_review | approved | no_notes_needed`

`BookPhase`:
`outline | chapters | completed`

### Shared response shapes

```text
User = {
  id: UUID, email: string, role: "user" | "admin",
  created_at: datetime, updated_at: datetime
}

Outline = {
  chapters: [{ chapter_number: int, title: string, brief: string }]
}

Book = {
  id: UUID, title: string, initial_notes: string | null,
  outline: Outline | null, outline_status: StageStatus,
  final_review_notes_status: StageStatus, phase: BookPhase,
  human_notes: string | null, owner_id: UUID | null,
  genre: string | null, tone: string | null,
  audience: string | null, length: string | null,
  created_at: datetime, updated_at: datetime
}

Chapter = {
  id: UUID, book_id: UUID, chapter_number: int, title: string,
  content: string | null, summary: string | null,
  status: StageStatus, human_notes: string | null,
  created_at: datetime, updated_at: datetime
}

Project = {
  id: UUID, name: string, description: string | null,
  owner_id: UUID, created_at: datetime, updated_at: datetime
}

Template = {
  id: UUID, name: string, description: string | null,
  template_json: object, category: string | null, is_public: boolean,
  created_by: UUID | null, created_at: datetime, updated_at: datetime
}
```

## Auth

### `POST /api/v1/auth/register`

- Auth: public
- Content-Type: `application/json`
- Body: `{ email: string, password: string }`
- Constraints: valid email; password length 8–128
- Returns `201`: `User`
- Errors: `400` if email exists or creation fails; `422` for validation

### `POST /api/v1/auth/login`

- Auth: public
- Content-Type: `application/x-www-form-urlencoded`
- Form fields: `username` (the user's email), `password`
- Returns `200`:
  `{ access_token: string, token_type: "bearer", expires_in: int }`
- Errors: `401` for incorrect email or password; `422` for malformed form data

### `GET /api/v1/auth/me`

- Auth: Bearer token
- Returns `200`: `User`
- Errors: `401` for a missing, invalid, or expired token

## Books and generation

All routes in this section require a Bearer token. Non-admin users can only
access books they own; ownership failures return `403`.

### `POST /api/v1/books`

- Body:
  `{ title: string, initial_notes?: string, auto_approve_outline?: boolean, genre?: string, tone?: string, audience?: string, length?: string }`
- `title` length: 1–500
- Creates a user-owned book and generates its outline synchronously
- Returns `200`: `Book`
- Errors: `401`, `422`; `502` if generation or persistence fails

### `POST /api/v1/generate-outline`

- Body:
  `{ title: string, notes?: string, genre?: string, tone?: string, audience?: string, length?: string }`
- Creates a user-owned book with an `outline_review` outline
- Returns `200`: `Book`
- Errors: `401`, `422`; `502` if generation fails

### `POST /api/v1/generate-chapter`

- Body:
  `{ chapter_id: UUID, genre?: string, tone?: string, audience?: string, length?: string }`
- Generates content for an existing chapter cleared by a review gate
- Returns `200`: `Chapter`
- Errors: `401`, `403`, `404`; `409` if the chapter is not cleared

### `GET /api/v1/books`

- Returns `200`: `Book[]`
- Normal users receive their books only; admins receive all books
- Errors: `401`

### `GET /api/v1/books/{book_id}`

- Returns `200`: `Book`
- Errors: `401`, `403`, `404`

### `PATCH /api/v1/books/{book_id}/outline`

- Body: `{ human_notes: string, status?: StageStatus }`
- Default status: `approved`
- Approved/no-notes statuses move the book to the `chapters` phase
- Returns `200`: `Book`
- Errors: `401`, `403`, `404`, `422`

### `PATCH /api/v1/books/{book_id}/final-review`

- Body: `{ human_notes?: string, status?: StageStatus }`
- Default status: `no_notes_needed`
- `no_notes_needed` moves the book to the `completed` phase
- Returns `200`: `Book`
- Errors: `401`, `403`, `404`, `422`

### `POST /api/v1/books/{book_id}/chapters/next`

- Generates the next missing chapter from the approved outline
- Returns `200`: `Chapter`
- Errors: `400` if no chapters remain; `401`, `403`, `404`;
  `409` if the outline has not been approved; `502` if generation fails

### `GET /api/v1/books/{book_id}/chapters`

- Returns `200`: `Chapter[]`, ordered by chapter number
- Errors: `401`, `403`, `404`

### `PATCH /api/v1/chapters/{chapter_id}`

- Body: `{ human_notes?: string, status?: StageStatus }`
- Default status: `approved`
- Returns `200`: `Chapter`
- Errors: `401`, `403`, `404`, `422`

### `POST /api/v1/chapters/{chapter_id}/regenerate`

- Regenerates content using the outline, prior summaries, and human notes
- Returns `200`: `Chapter`
- Errors: `401`, `403`, `404`; `502` if regeneration fails

### `POST /api/v1/books/{book_id}/chapters/{chapter_id}/moderate`

- Returns `200`: `Chapter`
- Sets status to `approved` or `pending_notes`
- Errors: `400` if the chapter is not part of the book; `401`, `403`, `404`

### `GET /api/v1/books/{book_id}/draft`

- Returns `200`:
  `{ book: Book, chapters: Chapter[], full_text: string }`
- Does not require final review to be complete
- Errors: `401`, `403`, `404`

### `GET /api/v1/books/{book_id}/compile`

- Returns `200`: downloadable UTF-8 plain-text file
- Header: `Content-Disposition: attachment; filename="..."`
- Errors: `401`, `403`, `404`; `409` unless final review is
  `no_notes_needed`

### Export routes

- `GET /api/v1/books/{book_id}/export/pdf`
- `GET /api/v1/books/{book_id}/export/epub`
- `GET /api/v1/books/{book_id}/export/markdown`
- `GET /api/v1/books/{book_id}/export/html`

Each returns `200`: `{ url: string }`. The URL is a relative path under
`/exports`. Exports require final review to be `no_notes_needed`.

Errors: `400` if there are no chapters; `401`, `403`, `404`.

## Health and analytics

### `GET /api/v1/health`

- Auth: public
- Returns `200`:
  `{ status: string, message: string, supabase: { status: string, detail: string | null }, openrouter: { status: string, detail: string | null } }`

### `GET /api/v1/stats`

- Auth: Bearer token
- Returns `200`:
  `{ total_books: int, total_chapters: int, books: [{ book_id: UUID, title: string, chapters_count: int, estimated_token_usage: int }], writing_style_analytics: { genre_distribution: object, tone_distribution: object, audience_distribution: object, length_distribution: object }, token_consumption_trends: [{ date: "YYYY-MM-DD", estimated_tokens: int }] }`
- Data is scoped to the current user; admins receive aggregate data
- Errors: `401`; `500` if analytics retrieval fails

## Projects

Project collection routes end with `/`.

### `POST /api/v1/projects/`

- Auth: Bearer token
- Body: `{ name: string, description?: string }`
- Returns `201`: `Project`
- Errors: `401`, `422`

### `GET /api/v1/projects/`

- Auth: Bearer token
- Returns `200`: `Project[]` owned by the current user
- Errors: `401`

The remaining project routes accept either a Bearer token or an `x-api-key`
belonging to that project:

### `GET /api/v1/projects/{proj_id}`

- Returns `200`: `Project`
- Errors: `401`, `403`, `404`

### `PATCH /api/v1/projects/{proj_id}`

- Body: `{ name?: string, description?: string }`
- Returns `200`: `Project`
- Errors: `401`, `403`, `404`, `422`

### `DELETE /api/v1/projects/{proj_id}`

- Returns `204` with no body
- Errors: `401`, `403`, `404`

### `POST /api/v1/projects/{proj_id}/keys`

- Returns `200`:
  `{ api_key: string, key_id: UUID, expires_at: datetime | null }`
- The raw API key is returned only at creation
- Errors: `401`, `403`, `404`

### `GET /api/v1/projects/{proj_id}/keys`

- Returns `200`:
  `{ keys: [{ id: UUID, created_at: datetime, expires_at: datetime | null, revoked: boolean }] }`
- Errors: `401`, `403`, `404`

### `PATCH /api/v1/projects/{proj_id}/keys/{key_id}`

- Query parameters: `revoke?: boolean`, `expires_at?: datetime`
- At least one effective update is required
- Returns `200`:
  `{ id: UUID, created_at: datetime, expires_at: datetime | null, revoked: boolean }`
- Errors: `400` if no update is supplied; `401`, `403`, `404`, `422`

### `DELETE /api/v1/projects/{proj_id}/keys/{key_id}`

- Returns `204` with no body
- Errors: `401`, `403`, `404`

## Templates

All template routes require a Bearer token.

### `POST /api/v1/templates`

- Body:
  `{ name: string, description?: string, template_json: object, category?: string, is_public?: boolean, created_by?: UUID }`
- `created_by` defaults to the authenticated user's ID when omitted
- Returns `201`: `Template`
- Errors: `401`, `422`

### `GET /api/v1/templates`

- Query: `category?: string`, `public_only?: boolean` (default `true`)
- Returns `200`: `{ templates: Template[] }`
- Errors: `401`, `422`

### `GET /api/v1/templates/{template_id}`

- Returns `200`: `Template`
- Errors: `401`, `404`

### `PATCH /api/v1/templates/{template_id}`

- Body:
  `{ name?: string, description?: string, template_json?: object, category?: string, is_public?: boolean }`
- Returns `200`: `Template`
- Errors: `401`, `404`, `422`

### `DELETE /api/v1/templates/{template_id}`

- Returns `204` with no body
- Errors: `401`, `404`

## Webhooks

Webhook receiver routes are currently public.

### `POST /api/v1/webhooks/outline-approved`

- Body:
  `{ book_id: UUID, book_title: string, outline_data: object, approved_by?: string, approval_notes?: string }`
- Returns `204` with no body
- Errors: `422` for validation

### `POST /api/v1/webhooks/chapter-completed`

- Body:
  `{ book_id: UUID, book_title: string, chapter_number: int, chapter_title: string, chapter_summary?: string, completed_by?: string }`
- Returns `204` with no body
- Errors: `422` for validation

## Public utility routes

- `GET /` → `{ docs: "/docs", health: "/api/v1/health" }`
- `GET /docs` → Swagger UI
- `GET /redoc` → ReDoc
- `GET /openapi.json` → generated OpenAPI document
- `GET /exports/{filename}` → generated export file