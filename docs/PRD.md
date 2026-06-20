# Automated Book Generation System - Product Requirements Document

## Goal
Build an end‑to‑end pipeline that takes source content (e.g., markdown, LaTeX, or plain text) and automatically produces a polished, publish-ready book in multiple output formats (PDF, EPUB, MOBI, HTML) with human-in-the-loop review gates.

## Core Features Implemented

### 1. Project & User Management
- User registration and authentication (JWT-based)
- Project creation and ownership
- API key management for project-level access
- Role-based access control (user/admin)

### 2. Book Generation Pipeline
- **Outline Generation**: AI-generated book outlines with 5-8 chapters
- **Human-in-the-Loop Gates**: 
  - Outline approval required before chapter generation
  - Chapter-level approval before proceeding to next chapter
  - Final review clearance required for book compilation
- **Chapter Generation**: 
  - Sequential generation using prior chapter summaries for continuity
  - Style/tone controls (genre, tone, audience, length)
  - Automatic summarization for context chaining
- **Content Moderation**: Integrated moderation service for quality and appropriateness checking

### 3. Multi-Format Export
- PDF generation using WeasyPrint with styled templates
- EPUB generation using ebook-lib
- Markdown export with proper formatting
- HTML export with responsive design
- All exports require final review clearance

### 4. Template System
- Outline template creation and management
- Public/private template sharing
- Template categorization (fiction, non-fiction, academic, etc.)
- JSONB storage for outline structures

### 5. Analytics & Monitoring
- Writing style analytics (genre, tone, audience, length distribution)
- Token consumption trends over time
- Book and chapter counting
- Daily quota tracking per project
- Health check endpoints for Supabase and AI services

### 6. Integration & Extensibility
- Webhook system for Slack and CI/CD notifications
- Outline approved webhook triggers
- Chapter completed webhook triggers
- Configurable webhook URLs
- RESTful API with comprehensive OpenAPI/Swagger documentation
- Docker containerization support

### 7. Technical Architecture
- **Backend**: FastAPI with async support
- **Database**: Supabase (PostgreSQL) with Row Level Security
- **Storage**: Local file system for exports (configurable)
- **AI Service**: OpenRouter/LLM integration (configurable model)
- **Moderation**: Pluggable content validation service
- **Export**: Template-based generation with WeasyPrint and ebook-lib

## Human-in-the-Loop Workflow

1. **Book Creation**: User submits title and optional notes → System generates outline
2. **Outline Review**: Outline stays in `pending_review` status until human approves (sets to `approved` or `no_notes_needed`)
3. **Chapter Generation**: System generates chapters sequentially, each requiring approval before next can be generated
4. **Final Review**: After all chapters generated and approved, user must clear final review to enable compilation
5. **Export**: Book can be exported to multiple formats once final review is cleared

## Database Schema

### Books Table
- `id`: UUID (primary key)
- `title`: Text
- `initial_notes`: Text
- `outline`: JSONB (generated outline structure)
- `outline_status`: StageStatus enum (pending_review, approved, no_notes_needed, etc.)
- `final_review_notes_status`: StageStatus enum
- `phase`: BookPhase enum (outline, chapters, completed)
- `genre`, `tone`, `audience`, `length`: Text (for analytics)
- `human_notes`: Text (feedback from reviewers)
- `created_at`, `updated_at`: Timestamps

### Chapters Table
- `id`: UUID (primary key)
- `book_id`: UUID (foreign key to books)
- `chapter_number`: Integer
- `title`: Text
- `content`: Text (generated chapter content)
- `summary`: Text (AI-generated summary)
- `status`: StageStatus enum
- `human_notes`: Text
- `created_at`, `updated_at`: Timestamps
- Unique constraint on (`book_id`, `chapter_number`)

### Additional Tables
- `outline_templates`: For storing reusable outline structures
- `api_keys`: For project-level API key management
- `usage_quota`: For daily token tracking per project
- `projects`: For user project ownership
- `users`: For authentication and authorization

## API Endpoints

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - JWT authentication
- `GET /auth/me` - Get current user

### Project Management
- `POST /projects/` - Create project
- `GET /projects/{id}` - Get project
- `PATCH /projects/{id}` - Update project
- `DELETE /projects/{id}` - Delete project
- `POST /projects/{id}/keys` - Generate API key
- `GET /projects/{id}/keys` - List API keys
- `PATCH /projects/{id}/keys/{key_id}` - Manage API key
- `DELETE /projects/{id}/keys/{key_id}` - Delete API key

### Book Management
- `POST /books` - Create book and generate outline
- `GET /books` - List all books
- `GET /books/{id}` - Get specific book
- `PATCH /books/{id}/outline` - Update outline status (human review gate)
- `PATCH /books/{id}/final-review` - Update final review status
- `POST /books/{id}/chapters/next` - Generate next chapter
- `GET /books/{id}/chapters` - List chapters for book
- `PATCH /chapters/{id}` - Update chapter status (human review gate)
- `POST /chapters/{id}/regenerate` - Regenerate chapter with notes
- `POST /books/{id}/chapters/{chapter_id}/moderate` - Moderate chapter content
- `GET /books/{id}/compile` - Compile book as plain text (requires final review clearance)
- `GET /books/{id}/draft` - Get book draft with outline and chapters

### Generation Endpoints
- `POST /generate-outline` - Generate outline from title/notes
- `POST /generate-chapter` - Generate chapter when human gating allows

### Export Endpoints
- `GET /books/{id}/export/pdf` - Export as PDF
- `GET /books/{id}/export/epub` - Export as EPUB
- `GET /books/{id}/export/markdown` - Export as Markdown
- `GET /books/{id}/export/html` - Export as HTML

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

## Success Metrics

### Functional
- Support for books up to 1,000 pages without performance degradation
- Deterministic outputs: identical inputs produce identical books
- No external network calls during generation (all processing runs locally or within confined CI)
- Plug‑in architecture for custom templates, language models, and output formats

### Quality Targets
- Reduce manual formatting time by ≥ 80%
- Achieve ≤ 5% post-generation editorial corrections
- Support at least three output formats (PDF, EPUB, HTML) with single source input
- Provide web UI for authors and editors to comment, track changes, and approve final output

### Technical
- Horizontal scalability through stateless services
- Fault tolerance with retry/back-off logic in orchestration
- Comprehensive monitoring and observability (logging, metrics, tracing)
- Secure by design with proper authentication, authorization, and data protection

## Non-Functional Requirements

### Performance
- Response times under 2 seconds for API endpoints (excluding AI generation)
- Support for concurrent users/projects
- Efficient database querying with proper indexing

### Security
- JWT-based authentication for end-users
- API key-based authentication for service-to-service communication
- Row Level Security (RLS) in database for data isolation
- Input validation and sanitization
- Secure handling of API keys and secrets

### Reliability
- Automated health checks for all external services
- Graceful degradation when optional services unavailable
- Comprehensive error handling and logging
- Database connection pooling and retry mechanisms

### Maintainability
- Modular, service-oriented architecture
- Comprehensive API documentation (Swagger/OpenAPI)
- Clear separation of concerns (routing, services, models)
- Consistent code formatting and linting
- Dockerized deployment for consistent environments

## Future Enhancements (Planned)

1. **Multilingual Support** (Task 8 - Pending):
   - Language parameter for generation
   - Model routing based on language
   - Prompt templates for different languages
   - Spanish/French testing and validation

2. **Advanced Analytics Integration**:
   - Full integration of analytics dashboard with Supabase
   - Advanced metrics and visualization
   - Export of analytics reports

3. **Enhanced Collaboration Features**:
   - Real-time commenting system
   - Change tracking and version history
   - Role-based permissions for collaborators

4. **Advanced Export Options**:
   - Customizable templates and themes
   - Advanced EPUB features (metadata, cover generation)
   - Print-ready PDF options with bleed and crop marks

5. **AI Model Flexibility**:
   - Support for multiple LLM providers (OpenAI, Anthropic, local models)
   - Model fine-tuning capabilities
   - Cost optimization and token usage controls

## Conclusion

The Automated Book Generation System provides a comprehensive, production-ready platform for creating books with AI assistance while maintaining human oversight and quality control. The implemented features cover the complete lifecycle from ideation to export, with extensibility for future enhancements.