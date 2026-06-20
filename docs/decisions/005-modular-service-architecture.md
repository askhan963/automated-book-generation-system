# 005 - Adopt Modular Service Architecture

## Status
Accepted

## Context
As the Automated Book Generation System grew in functionality, we needed to organize the codebase to maintain clarity, testability, and separation of concerns. The system needed to handle:
- HTTP request routing and API endpoint management
- Business logic for book generation and workflow management
- Data access and persistence operations
- External service integrations (LLM, export, webhooks)
- Authentication and authorization
- Content moderation and validation
- Utility functions and shared components

Alternative architectural patterns considered:
- Monolithic single-file application (simple but doesn't scale)
- MVC (Model-View-Controller) pattern (traditional but less suited for APIs)
- Layered architecture (presentation, business, data layers) (good but can be rigid)
- Microservices architecture (highly scalable but excessive complexity for MVP)
- Modular monolith with clear boundaries (balanced approach)
- Event-driven architecture (powerful but adds complexity for current needs)
- Clean/Hexagonal architecture (excellent separation but potentially over-engineered)

## Decision
Adopted a modular service architecture with clearly defined layers:
1. **API Layer** (`app/api/`): Handles HTTP routing, request/response validation, and endpoint documentation
2. **Service Layer** (`app/services/`): Contains business logic encapsulated in domain-specific services
3. **Data Layer** (`app/services/db_service.py` + `sql/`): Manages data persistence and retrieval
4. **Model Layer** (`app/models.py`): Defines data contracts, validation, and serialization
5. **Core Layer** (`app/core/`): Configuration, utilities, and cross-cutting concerns
6. **Configuration Layer** (`app/core/config.py`): Centralized settings management

Each service has a single responsibility:
- `ai_service.py`: All LLM interactions and text generation
- `db_service.py`: All database operations and data access patterns
- `user_service.py`: Authentication, authorization, and API key management
- `export_service.py`: Multi-format document generation (PDF, EPUB, HTML, Markdown)
- `moderation_service.py`: Content validation and safety checking
- `project_service.py`: Project lifecycle and resource management

## Consequences
### Positive
- Clear separation of concerns makes code easier to understand and modify
- Services can be developed, tested, and maintained independently
- Reduced coupling between different functional areas
- Easier to mock dependencies during testing
- Clear ownership and responsibility for each code section
- Scalable pattern that can grow with additional features
- Facilitates code reuse and reduces duplication
- Enables different teams to work on different services with minimal conflict

### Negative
- Initial setup overhead compared to simpler architectures
- Potential for over-abstraction if service boundaries are not well-defined
- Need to manage inter-service communication patterns
- Slightly more complex dependency injection or service location
- May require more files to navigate for simple changes

### Neutral
- Follows common Python/FastAPI project structures
- Aligns with domain-driven design principles at a modest level
- Provides foundation that could evolve toward microservices if needed
- Uses dependency injection patterns naturally through imports and function parameters

## Related Documents
- [ARCHITECTURE.md](../ARCHITECTURE.md) - Detailed system architecture overview
- Source code organization in `app/` directory
- [API.md](../API.md) - API layer documentation showing route organization
- Service implementations in `app/services/` directory
- Model definitions in `app/models.py`
- Configuration in `app/core/config.py`