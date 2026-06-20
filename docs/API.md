# API Contract Reference

This document provides a comprehensive reference for the Automated Book Generation System API. All endpoints are prefixed with `/api/v1` unless otherwise specified.

## Base URL
```
http://localhost:8000
```

## Authentication

### JWT Authentication
For user-facing endpoints, authenticate using a Bearer token obtained from `/auth/login`:
```
Authorization: Bearer <jwt_token>
```

### API Key Authentication
For service-to-service authentication, use an API key tied to a specific project:
```
X-API-Key: <api_key>
```

## Status Codes
- `200`: Successful request
- `201`: Resource created
- `204`: No content (successful deletion or update with no response body)
- `400`: Bad request (validation error, missing parameters)
- `401`: Unauthenticated (missing or invalid authentication)
- `403`: Forbidden (authenticated but insufficient permissions)
- `404`: Not found (resource doesn't exist)
- `409`: Conflict (resource state prevents operation)
- `422`: Unprocessable entity (schema validation failure)
- `500`: Internal server error
- `502`: Bad gateway (external service failure)
- `501`: Not implemented (feature not available)

## Common Response Formats

### Error Response
```json
{
  "detail": "Error message describing what went wrong"
}
```

### Paginated Response
```json
{
  "data": [...],
  "total": 100,
  "page": 1,
  "per_page": 20
}
```

## Endpoints

### Authentication
- `POST /auth/register` - Register a new user
- `POST /auth/login` - Authenticate and obtain JWT token
- `GET /auth/me` - Get current user profile

### Project Management
- `POST /projects/` - Create a new project
- `GET /projects/{id}` - Get project details
- `PATCH /projects/{id}` - Update project
- `DELETE /projects/{id}` - Delete project
- `POST /projects/{id}/keys` - Generate new API key for project
- `GET /projects/{id}/keys` - List project API keys
- `PATCH /projects/{id}/keys/{key_id}` - Manage API key (revoke, extend)
- `DELETE /projects/{id}/keys/{key_id}` - Delete API key

### Book Management
- `POST /books` - Create book and generate outline
- `GET /books` - List all books (newest first)
- `GET /books/{id}` - Get book details
- `PATCH /books/{id}/outline` - Update outline review status (human gate)
- `PATCH /books/{id}/final-review` - Update final review status
- `POST /books/{id}/chapters/next` - Generate next chapter
- `GET /books/{id}/chapters` - List all chapters for book
- `PATCH /chapters/{id}` - Update chapter review status (human gate)
- `POST /chapters/{id}/regenerate` - Regenerate chapter with notes
- `POST /books/{id}/chapters/{chapter_id}/moderate` - Moderate chapter content
- `GET /books/{id}/compile` - Compile book as plain text (requires final review clearance)
- `GET /books/{id}/draft` - Get book draft with outline and chapters

### AI Generation
- `POST /generate-outline` - Generate book outline from title/notes
- `POST /generate-chapter` - Generate chapter when human gating allows

### Export
- `GET /books/{id}/export/pdf` - Export book as PDF
- `GET /books/{id}/export/epub` - Export book as EPUB
- `GET /books/{id}/export/markdown` - Export book as Markdown
- `GET /books/{id}/export/html` - Export book as HTML

### Template Management
- `POST /templates/` - Create outline template
- `GET /templates/` - List templates (with filtering)
- `GET /templates/{id}` - Get specific template
- `PATCH /templates/{id}` - Update template
- `DELETE /templates/{id}` - Delete template

### Analytics & Health
- `GET /stats` - Get analytics dashboard statistics
- `GET /health` - Health check for Supabase and AI services
- `GET /` - Root endpoint with docs and health links

### Webhooks
- `POST /api/v1/webhooks/outline-approved` - Outline approval notifications
- `POST /api/v1/webhooks/chapter-completed` - Chapter completion notifications

## Data Models

### BookResponse
```json
{
  "id": "uuid",
  "title": "string",
  "initial_notes": "string|null",
  "outline": "object|null",
  "outline_status": "string",
  "final_review_notes_status": "string",
  "phase": "string",
  "human_notes": "string|null",
  "genre": "string|null",
  "tone": "string|null",
  "audience": "string|null",
  "length": "string|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### ChapterResponse
```json
{
  "id": "uuid",
  "book_id": "uuid",
  "chapter_number": "integer",
  "title": "string",
  "content": "string|null",
  "summary": "string|null",
  "status": "string",
  "human_notes": "string|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### TemplateResponse
```json
{
  "id": "uuid",
  "name": "string",
  "description": "string|null",
  "template_json": "object",
  "category": "string|null",
  "is_public": "boolean",
  "created_by": "uuid|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### HealthResponse
```json
{
  "status": "string",
  "message": "string",
  "supabase": {
    "status": "string",
    "detail": "string|null"
  },
  "openrouter": {
    "status": "string",
    "detail": "string|null"
  }
}
```

### StatsResponse
```json
{
  "total_books": "integer",
  "total_chapters": "integer",
  "books": [
    {
      "book_id": "uuid",
      "title": "string",
      "chapters_count": "integer",
      "estimated_token_usage": "integer"
    }
  ],
  "writing_style_analytics": {
    "genre_distribution": {"string": "integer"},
    "tone_distribution": {"string": "integer"},
    "audience_distribution": {"string": "integer"},
    "length_distribution": {"string": "integer"}
  },
  "token_consumption_trends": [
    {
      "date": "YYYY-MM-DD",
      "estimated_tokens": "integer"
    }
  ]
}
```

## Enumerations

### StageStatus
- `pending_notes` - Awaiting revision notes
- `pending_review` - Awaiting review/approval
- `outline_review` - Outline under review
- `approved` - Formally approved
- `no_notes_needed` - Approved without notes needed

### BookPhase
- `outline` - In outline creation phase
- `chapters` - In chapter generation phase
- `completed` - All chapters generated, awaiting final review

## Rate Limiting
API endpoints are subject to rate limiting based on project quota:
- Daily token limits enforced per project
- Usage tracked via `X-API-Key` or JWT-associated project
- `429` status returned when quota exceeded
- Quota information available in project management interface

## Versioning
API version is indicated in the URL path (`/api/v1/`). Breaking changes will result in version increment (`/api/v2/`). Non-breaking changes may be added to existing versions.

## Contact
For API questions or issues, refer to the project documentation or contact the development team.