# Automated Book Generation System - Architecture Document

## Overview
The Automated Book Generation System is built as a modular, service-oriented FastAPI backend that coordinates content ingestion, AI-assisted generation, human-in-the-loop review processes, and multi-format export capabilities. The architecture emphasizes separation of concerns, scalability, and maintainability.

## Core Components

### 1. API Layer (`app/api/`)
- **RESTful Entry Points**: All client interactions occur through well-defined HTTP endpoints
- **Router Organization**: Feature-based route organization (`routes.py`, `generation.py`, `webhooks.py`, `templates.py`, `projects.py`, `auth.py`)
- **Request/Response Models**: Pydantic models for data validation and serialization
- **Middleware**: CORS configuration for cross-origin requests
- **Static File Serving**: Export files served via `/exports` endpoint

### 2. Service Layer (`app/services/`)
Business logic is encapsulated in specialized services:

#### `ai_service.py`
- Interface to OpenRouter/LLM providers for text generation
- Outline generation (`generate_outline`)
- Chapter generation with continuity (`generate_chapter`)
- Chapter summarization (`summarize_chapter`)
- Content moderation integration
- Health checking for AI services
- Prompt engineering with style/tone controls

#### `db_service.py`
- Supabase client wrapper and connection management
- CRUD operations for books, chapters, projects, templates, API keys, usage tracking
- Transaction-like operations with error handling
- Specialized queries:
  - `get_next_outline_chapter` - finds next ungenerated chapter
  - `get_previous_chapter_summaries` - retrieves summarites for context chaining
  - `compile_book_text` - combines all chapters for export
  - Template management functions
  - Usage quota tracking

#### `user_service.py`
- User authentication and authorization
- Password hashing and verification (bcrypt)
- JWT token creation and validation
- API key generation and management (SHA-256 hashing)
- Project ownership verification
- Role-based access control (user/admin)
- Usage tracking and quota enforcement

#### `export_service.py`
- Multi-format export generation:
  - PDF: WeasyPrint with HTML/CSS templating
  - EPUB: ebook-lib library
  - Markdown: Simple text formatting
  - HTML: Responsive HTML templates
- File storage management (local exports directory)
- Filename generation and URL routing

#### `moderation_service.py`
- Content validation interface
- Currently implements profanity filter with blacklist
- Designed for easy replacement with external moderation APIs
- Raises HTTPException on validation failure

#### `project_service.py`
- Project lifecycle management (CRUD operations)
- API key management tied to projects
- Cascading deletes for related resources

### 3. Data Models (`app/models.py`)
Pydantic models defining:
- **Request Models**: Incoming API data validation
- **Response Models**: Outgoing API data serialization
- **Domain Models**: Core entities (BookResponse, ChapterResponse, etc.)
- **Enumerations**: StageStatus, BookPhase, Role
- **Specialized Models**: 
  - Template models (TemplateCreateRequest, TemplateResponse)
  - Auth models (UserCreateResponse, TokenResponse)
  - Project and API key models
  - Health check models

### 4. Database Schema (`sql/`)
PostgreSQL schema managed through Supabase:

#### Core Tables
- **books**: Stores book metadata, outline, review statuses, phase
- **chapters**: Stores chapter content, summaries, status, notes
- **outline_templates**: Reusable outline structures with categorization
- **projects**: User-owned containers for books and API keys
- **users**: Authentication and authorization
- **api_keys**: Secure API key storage (hashed)
- **usage_quota**: Daily token tracking per project

#### Custom Types
- `stage_status`: ENUM for workflow states (pending_review, approved, no_notes_needed, etc.)
- `book_phase`: ENUM for book lifecycle (outline, chapters, completed)

#### Triggers
- Automatic `updated_at` timestamp updates via triggers on books, chapters, and outline_tables

#### Security
- Row Level Security (RLS) policies enabling full API access (appropriate for backend-only exposure)
- Policies applied to books, chapters, and outline_templates tables

### 5. Webhook System (`app/api/webhooks.py`)
- Event-driven notifications for key lifecycle events
- **Outline Approved Webhook**: Notifies when book outline is approved
- **Chapter Completed Webhook**: Notifies when individual chapters are completed
- **CI/CD Integration**: Generic webhook sender for continuous integration systems
- **Slack Integration**: Formatted notifications for team communication
- Asynchronous HTTP client (httpx) for non-blocking webhook delivery
- Error handling with logging (webhook failures don't block main operations)

## Data Flow

### Book Creation and Outline Generation
1. Client calls `POST /books` with title and optional notes
2. Route handler validates request and calls `db_service.create_book`
3. AI service generates outline via `ai_service.generate_outline`
4. Outline status set based on configuration (auto-approve or pending review)
5. Book record saved with outline JSONB and initial status
6. Outline approved webhook optionally triggered

### Chapter Generation Process
1. Client calls `POST /books/{id}/chapters/next` for next chapter
2. Route validates book exists and outline is approved (`_ensure_outline_approved`)
3. Service determines next ungenerated chapter from outline
4. Creates chapter stub with initial status (pending_review or no_notes_needed)
5. Retrieves prior chapter summaries for context chaining
6. AI service generates chapter content using:
   - Book title
   - Chapter outline (number, title, brief)
   - Prior summaries for continuity
   - Human notes from outline/book (if any)
   - Style/tone parameters (genre, tone, audience, length)
7. AI service generates summary of created content
8. Chapter record updated with content, summary, and status
9. Chapter completed webhook optionally triggered

### Human-in-the-Loop Review Gates
- **Outline Approval**: Clients update outline status via `PATCH /books/{id}/outline`
  - Setting status to `approved` or `no_notes_needed` allows chapter generation to proceed
  - Triggers outline approved webhook
- **Chapter Approval**: Clients update chapter status via `PATCH /chapters/{id}`
  - Setting status to `approved` or `no_notes_needed` allows next chapter generation
  - Triggers chapter completed webhook
- **Final Review**: Clients update final review status via `PATCH /books/{id}/final-review`
  - Setting status to `no_notes_needed` enables book compilation and export
  - Sets book phase to `completed`

### Export Process
1. Client calls export endpoint (e.g., `GET /books/{id}/export/pdf`)
2. Route validates book exists and final review is cleared
3. Service retrieves book and all chapters
4. Export service generates appropriate format:
   - PDF: HTML template → WeasyPrint → PDF bytes
   - EPUB: HTML content → ebook-lib → EPUB bytes
   - Markdown/HTML: Template string → formatted output
5. Export file saved to local exports directory
6. URL returned for client download

### Moderation Integration
1. Clients can trigger moderation via `POST /books/{id}/chapters/{chapter_id}/moderate`
2. Service retrieves chapter content
3. Moderation service validates content against rules
4. On success: Chapter status set to approved with moderation note
5. On failure: Chapter status set to pending_notes with rejection reason
6. Chapter updated with appropriate status and notes

## Cross-Cutting Concerns

### Configuration (`app/core/config.py`)
- Centralized configuration management via Pydantic Settings
- Environment variable loading with validation
- Separate settings for development, testing, production
- Configuration includes:
  - Database connection (Supabase URL and key)
  - AI service settings (OpenRouter API key, model, base URL)
  - Security settings (JWT secret, expiration)
  - Service URLs (webhook URLs for Slack, CI/CD)
  - Feature flags (require_human_review, auto_approve_outline)
  - File system paths (export directory)

### Error Handling
- Consistent error response format across all endpoints
- HTTPException usage for API-level errors
- Supabase error translation via `supabase_errors.py`
- Validation errors automatically handled by FastAPI/Pydantic
- Logging throughout for debugging and monitoring

### Security
- Authentication via JWT (user-facing) or API key (service-facing)
- Password hashing using bcrypt (industry standard)
- API keys stored as SHA-256 hashes (never plaintext)
- Role-based access control enforced in route dependencies
- Input validation and sanitization at API boundary
- CORS configuration for controlled cross-origin access
- SQL injection prevention via Supabase ORM/parameterized queries

### Observability
- Health check endpoints (`/health`) for dependency status
- Comprehensive logging throughout all layers
- Structured error reporting with context
- Metrics collection possible through usage tracking
- Request timing and performance monitoring hooks available

## Scalability and Deployment

### Horizontal Scaling
- Stateless services enable horizontal scaling
- Database connection pooling through Supabase
- External service calls (AI, webhooks) designed for concurrency
- File-based exports can be offloaded to object storage (S3, etc.)

### Deployment Options
- **Local Development**: `./run.sh` or `uvicorn app.main:app --reload`
- **Docker Containerization**: `docker compose up --build -d`
- **Production Deployment**: Compatible with any WSGI/ASGI server
- **Cloud Deployment**: Works on AWS, GCP, Azure, or any VPS

### Extensibility Points
1. **AI Service**: Swap LLM providers by modifying `get_openai_client` and `_complete`
2. **Moderation**: Replace `validate_content` with external API calls
3. **Export**: Add new formats by extending `export_service.py`
4. **Webhooks**: Add new notification types in `webhooks.py`
5. **Storage**: Replace local file storage with cloud storage (S3, GCS)
6. **Caching**: Add Redis layer for frequent queries (summaries, templates)
7. **Analytics**: Enhance `/stats` endpoint with more sophisticated metrics

## Communication Patterns

### Synchronous
- HTTP REST API for client interactions
- Direct service-to-service calls within request scope
- Database queries via Supabase client

### Asynchronous
- Webhook delivery using `httpx.AsyncClient`
- Background task potential (not currently implemented but designed for)
- Event-driven architecture through webhook system

## Technology Stack

### Core Framework
- **FastAPI**: Modern, async-capable Python web framework
- **Pydantic**: Data validation and settings management
- **Uvicorn**: ASGI server for production deployment

### Database & Storage
- **Supabase**: Hosted PostgreSQL with real-time capabilities
- **SQLAlchemy-compatible**: Through Supabase Python client
- **Local File System**: Export storage (easily replaceable)

### AI & NLP
- **OpenRouter**: Unified API for multiple LLM providers
- **OpenAI GPT Models**: Default text generation and summarization
- **Configurable Models**: Easy switching between different LLMs

### Security
- **bcrypt**: Password hashing
- **python-jose**: JWT creation and validation
- **hashlib**: SHA-256 for API key storage
- **passlib**: Password hashing context

### Export & Document Generation
- **WeasyPrint**: HTML/CSS to PDF conversion
- **ebook-lib**: EPUB generation and manipulation

### Development & Operations
- **Docker**: Containerization for consistent deployment
- **docker-compose**: Multi-service orchestration
- **Git**: Version control
- **Python 3.8+**: Language runtime

## Design Principles

### Separation of Concerns
- Clear division between API routing, business logic, and data access
- Services encapsulate specific domains (AI, DB, export, etc.)
- Models define data contracts between layers

### Loose Coupling
- Services communicate through well-defined interfaces
- Dependency injection patterns where appropriate
- Configuration-driven behavior
- Pluggable components (moderation, export formats)

### Maintainability
- Consistent code organization and naming conventions
- Comprehensive type hints for IDE support
- Modular structure enables independent development
- Clear documentation through code structure and docstrings

### Testability
- Dependency injection facilitates mocking
- Clear service boundaries for unit testing
- API endpoints can be tested in isolation
- Database operations wrapped for easy mocking

### Security by Design
- Defense in depth with multiple security layers
- Principle of least privilege in database access
- Secure defaults for authentication and authorization
- Regular dependency updates recommended

This architecture provides a solid foundation for a scalable, maintainable book generation system that can evolve with changing requirements while maintaining reliability and security.