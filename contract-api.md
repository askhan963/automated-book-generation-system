# API Contract Reference
Last updated: 2026-05-15

## Auth

POST /api/v1/auth/login
  Auth: none (public)
  Body: { email: str, password: str }
  Returns 200: { data: { access_token: str, refresh_token: str, token_type: string, expires_in: int } }
  Errors: 401 if email not found or password wrong

POST /api/v1/auth/register
  Auth: none (public)
  Body: { email: str, password: str, full_name?: str }
  Returns 201: { data: { id: string, email: string, full_name?: string, is_active: boolean, created_at: string, updated_at: string } }
  Errors: 400 if email invalid or password too short

POST /api/v1/auth/refresh
  Auth: none (public)
  Body: { refresh_token: str }
  Returns 200: { data: { access_token: str, token_type: string, expires_in: int } }
  Errors: 401 if refresh token invalid or expired

## Books

POST /api/v1/books
  Auth: required (Bearer token)
  Body: { title: str, initial_notes?: str, genre?: str, tone?: str, audience?: str, length?: str, auto_approve_outline?: bool }
  Returns 201: { data: { id: string, title: string, outline?: object, outline_status: string, final_review_notes_status: string, phase: string, created_at: string, updated_at: string } }
  Errors: 400 if validation fails, 401 if unauthenticated

POST /api/v1/generate-outline
  Auth: required (Bearer token)
  Body: { title: str, notes?: str }
  Returns 200: { data: { id: string, title: string, outline?: object, outline_status: string, final_review_notes_status: string, phase: string, created_at: string, updated_at: string } }
  Errors: 400 if validation fails, 401 if unauthenticated, 404 if book not found

POST /api/v1/generate-chapter
  Auth: required (Bearer token)
  Body: { book_id: string, chapter_number: int, title: str, summary?: str, content?: str }
  Returns 200: { data: { id: string, book_id: string, chapter_number: int, title: str, content?: string, summary?: string, status: string, human_notes?: string, created_at: string, updated_at: string } }
  Errors: 400 if validation fails, 401 if unauthenticated, 403 if not authorized for book, 404 if book/chapter not found

GET /api/v1/books
  Auth: required (Bearer token)
  Returns 200: { data: [ { id: string, title: string, outline?: object, outline_status: string, final_review_notes_status: string, phase: string, created_at: string, updated_at: string } ] }
  Errors: 401 if unauthenticated

GET /api/v1/books/{book_id}
  Auth: required (Bearer token)
  Returns 200: { data: { id: string, title: string, outline?: object, outline_status: string, final_review_notes_status: string, phase: string, created_at: string, updated_at: string } }
  Errors: 401 if unauthenticated, 404 if book not found

PATCH /api/v1/books/{book_id}/outline
  Auth: required (Bearer token)
  Body: { notes?: str, outline_status?: "outline_draft" | "outline_review" | "outline_approved" }
  Returns 200: { data: { id: string, title: string, outline?: object, outline_status: string, final_review_notes_status: string, phase: string, created_at: string, updated_at: string } }
  Errors: 400 if validation fails, 401 if unauthenticated, 403 if not authorized for book, 404 if book not found

PATCH /api/v1/books/{book_id}/final-review
  Auth: required (Bearer token)
  Body: { final_review_notes_status: "no notes" | "notes pending" | "addressed" }
  Returns 200: { data: { id: string, title: string, outline?: object, outline_status: string, final_review_notes_status: string, phase: string, created_at: string, updated_at: string } }
  Errors: 400 if validation fails, 401 if unauthenticated, 403 if not authorized for book, 404 if book not found

POST /api/v1/books/{book_id}/chapters/next
  Auth: required (Bearer token)
  Returns 200: { data: { id: string, book_id: string, chapter_number: int, title: str, content?: string, summary?: string, status: string, human_notes?: string, created_at: string, updated_at: string } }
  Errors: 401 if unauthenticated, 403 if not authorized for book, 404 if book not found, 409 if no approved chapters to build upon

GET /api/v1/books/{book_id}/chapters
  Auth: required (Bearer token)
  Returns 200: { data: [ { id: string, book_id: string, chapter_number: int, title: string, content?: string, summary?: string, status: string, human_notes?: string, created_at: string, updated_at: string } ] }
  Errors: 401 if unauthenticated, 404 if book not found

PATCH /api/v1/chapters/{chapter_id}
  Auth: required (Bearer token)
  Body: { notes?: str, status?: "draft" | "approved" | "revision_requested" | "no_notes_needed" }
  Returns 200: { data: { id: string, book_id: string, chapter_number: int, title: string, content?: string, summary?: string, status: string, human_notes?: string, created_at: string, updated_at: string } }
  Errors: 400 if validation fails, 401 if unauthenticated, 403 if not authorized for chapter, 404 if chapter not found

POST /api/v1/chapters/{chapter_id}/regenerate
  Auth: required (Bearer token)
  Returns 200: { data: { id: string, book_id: string, chapter_number: int, title: str, content?: string, summary?: string, status: string, human_notes?: string, created_at: string, updated_at: string } }
  Errors: 401 if unauthenticated, 403 if not authorized for chapter, 404 if chapter not found

POST /api/v1/books/{book_id}/chapters/{chapter_id}/moderate
  Auth: required (Bearer token)
  Returns 200: { data: { id: string, book_id: string, chapter_number: int, title: str, content?: string, summary?: string, status: string, human_notes?: string, created_at: string, updated_at: string } }
  Errors: 401 if unauthenticated, 403 if not authorized for chapter/book, 404 if book/chapter not found

GET /api/v1/books/{book_id}/compile
  Auth: required (Bearer token)
  Returns 200: plain text file (Content-Type: text/plain; charset=utf-8)
  Errors: 401 if unauthenticated, 403 if not authorized for book, 404 if book not found, 409 if final review not complete

GET /api/v1/books/{book_id}/draft
  Auth: required (Bearer token)
  Returns 200: { data: { id: string, title: string, outline?: object, chapters: [ { id: string, chapter_number: int, title: string, content: string, summary: string, status: string } ], created_at: string, updated_at: string } }
  Errors: 401 if unauthenticated, 404 if book not found

GET /api/v1/books/{book_id}/export/pdf
  Auth: required (Bearer token)
  Returns 200: { data: { url: string } }
  Errors: 401 if unauthenticated, 403 if not authorized for book, 404 if book not found, 409 if final review not complete

GET /api/v1/books/{book_id}/export/epub
  Auth: required (Bearer token)
  Returns 200: { data: { url: string } }
  Errors: 401 if unauthenticated, 403 if not authorized for book, 404 if book not found, 409 if final review not complete

GET /api/v1/books/{book_id}/export/markdown
  Auth: required (Bearer token)
  Returns 200: { data: { url: string } }
  Errors: 401 if unauthenticated, 403 if not authorized for book, 404 if book not found, 409 if final review not complete

GET /api/v1/books/{book_id}/export/html
  Auth: required (Bearer token)
  Returns 200: { data: { url: string } }
  Errors: 401 if unauthenticated, 403 if not authorized for book, 404 if book not found, 409 if final review not complete

GET /api/v1/health
  Auth: none (public)
  Returns 200: { data: { status: string, message: string, supabase: { status: string, detail?: string }, openrouter: { status: string, detail?: string } } }

GET /api/v1/stats
  Auth: required (Bearer token)
  Returns 200: { data: { total_books: int, total_chapters: int, books: [ { book_id: string, title: string, chapters_count: int, estimated_token_usage: int } ], writing_style_analytics: { genre_distribution: { string: int }, tone_distribution: { string: int }, audience_distribution: { string: int }, length_distribution: { string: int } }, token_consumption_trends: [ { date: string, estimated_tokens: int } ] } }
  Errors: 401 if unauthenticated

## Projects

POST /api/v1/projects/
  Auth: required (Bearer token)
  Body: { name: string, description?: string }
  Returns 201: { data: { id: string, name: string, description?: string, owner_id: string, created_at: string, updated_at: string } }
  Errors: 400 if validation fails, 401 if unauthenticated

GET /api/v1/projects/{proj_id}
  Auth: required (Bearer token or API key)
  Returns 200: { data: { id: string, name: string, description?: string, owner_id: string, created_at: string, updated_at: string } }
  Errors: 401 if unauthenticated, 403 if not authorized for project, 404 if project not found

PATCH /api/v1/projects/{proj_id}
  Auth: required (Bearer token or API key)
  Body: { name?: string, description?: string }
  Returns 200: { data: { id: string, name: string, description?: string, owner_id: string, created_at: string, updated_at: string } }
  Errors: 400 if validation fails, 401 if unauthenticated, 403 if not authorized for project, 404 if project not found

DELETE /api/v1/projects/{proj_id}
  Auth: required (Bearer token or API key)
  Returns 204: (no content)
  Errors: 401 if unauthenticated, 403 if not authorized for project, 404 if project not found

POST /api/v1/projects/{proj_id}/keys
  Auth: required (Bearer token or API key)
  Returns 200: { data: { api_key: string, key_id: string, expires_at?: string, revoked: boolean } }
  Errors: 401 if unauthenticated, 403 if not authorized for project, 404 if project not found

GET /api/v1/projects/{proj_id}/keys
  Auth: required (Bearer token or API key)
  Returns 200: { data: { keys: [ { id: string, created_at: string, expires_at?: string, revoked: boolean } ] } }
  Errors: 401 if unauthenticated, 403 if not authorized for project, 404 if project not found

PATCH /api/v1/projects/{proj_id}/keys/{key_id}
  Auth: required (Bearer token or API key)
  Query: revoke?: boolean, expires_at?: string
  Returns 200: { data: { id: string, created_at: string, expires_at?: string, revoked: boolean } }
  Errors: 400 if validation fails, 401 if unauthenticated, 403 if not authorized for project, 404 if project not found or key not found

DELETE /api/v1/projects/{proj_id}/keys/{key_id}
  Auth: required (Bearer token or API key)
  Returns 204: (no content)
  Errors: 401 if unauthenticated, 403 if not authorized for project, 404 if project not found or key not found

## Templates

POST /api/v1/templates
  Auth: required (Bearer token)
  Body: { name: string, content: string, category?: string, is_public?: boolean }
  Returns 201: { data: { id: string, name: string, content: string, category?: string, is_public: boolean, created_at: string, updated_at: string } }
  Errors: 400 if validation fails, 401 if unauthenticated

GET /api/v1/templates
  Auth: required (Bearer token)
  Query: category?: string, public_only?: boolean
  Returns 200: { data: { templates: [ { id: string, name: string, content: string, category?: string, is_public: boolean, created_at: string, updated_at: string } ], total: int } }
  Errors: 401 if unauthenticated

GET /api/v1/templates/{template_id}
  Auth: required (Bearer token)
  Returns 200: { data: { id: string, name: string, content: string, category?: string, is_public: boolean, created_at: string, updated_at: string } }
  Errors: 401 if unauthenticated, 404 if template not found

PATCH /api/v1/templates/{template_id}
  Auth: required (Bearer token)
  Body: { name?: string, content?: string, category?: string, is_public?: boolean }
  Returns 200: { data: { id: string, name: string, content: string, category?: string, is_public: boolean, created_at: string, updated_at: string } }
  Errors: 400 if validation fails, 401 if unauthenticated, 404 if template not found

DELETE /api/v1/templates/{template_id}
  Auth: required (Bearer token)
  Returns 204: (no content)
  Errors: 401 if unauthenticated, 404 if template not found

## Webhooks

POST /api/v1/webhooks/outline-approved
  Auth: required (Bearer token)
  Body: { book_id: string, title: string, outline: object }
  Returns 204: (no content)
  Errors: 400 if validation fails, 401 if unauthenticated

POST /api/v1/webhooks/chapter-completed
  Auth: required (Bearer token)
  Body: { book_id: string, chapter_id: string, chapter_number: int, title: string, content: string, summary: string }
  Returns 204: (no content)
  Errors: 400 if validation fails, 401 if unauthenticated