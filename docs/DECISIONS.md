# Architecture Decision Records (ADRs)

This document serves as the index for Architecture Decision Records (ADRs) that capture key technical decisions made during the development of the Automated Book Generation System backend. Each ADR follows the format:

```
# [ADR Number] - Title

## Status
Accepted | Superseded | Deprecated | Proposed

## Context
What Issue or requirement led to this decision?

## Decision
What change or approach was selected?

## Consequences
What are the impacts of this decision? (positive, negative, and neutral)

## Related Documents
Links to other ADRs, specifications, or source code that elaborate on this decision.
```

## How to Contribute
1. Create a new file in `docs/decisions/` named `NNN-descriptive-title.md` where NNN is the next sequential number
2. Follow the ADR template above
3. Add a link to this index in the "Related Documents" section when appropriate
4. Update the status as decisions evolve

## Recorded Decisions

| ID | Title | Status | Date |
|----|-------|--------|------|
| [001](docs/decisions/001-use-fastapi-framework.md) | Use FastAPI as the Web Framework | Accepted | 2024-01-15 |
| [002](docs/decisions/002-supabase-as-primary-database.md) | Use Supabase as Primary Database | Accepted | 2024-01-16 |
| [003](docs/decisions/003-human-in-the-loop-review-gates.md) | Implement Human-in-the-Loop Review Gates | Accepted | 2024-01-17 |
| [004](docs/decisions/004-openrouter-for-llm-integration.md) | Use OpenRouter for LLM Integration | Accepted | 2024-01-18 |
| [005](docs/decisions/005-modular-service-architecture.md) | Adopt Modular Service Architecture | Accepted | 2024-01-19 |
| [006](docs/decisions/006-jwt-and-api-key-authentication.md) | Use JWT and API Key Authentication | Accepted | 2024-01-20 |
| [007](docs/decisions/007-weasyprint-for-pdf-generation.md) | Use WeasyPrint for PDF Generation | Accepted | 2024-01-21 |
| [008](docs/decisions/008-async-webhook-delivery.md) | Implement Asynchronous Webhook Delivery | Accepted | 2024-01-22 |

## Decision Directory Structure

To add new ADRs:
```
docs/
├── DECISIONS.md              # This index file
└── decisions/
    ├── 001-use-fastapi-framework.md
    ├── 002-supabase-as-primary-database.md
    ├── 003-human-in-the-loop-review-gates.md
    ├── 004-openrouter-for-llm-integration.md
    ├── 005-modular-service-architecture.md
    ├── 006-jwt-and-api-key-authentication.md
    ├── 007-weasyprint-for-pdf-generation.md
    ├── 008-async-webhook-delivery.md
    └── NNN-descriptive-title.md  # Next ADR
```

## Example ADR Template

For reference when creating new decisions:

````markdown
# 001 - Use FastAPI as the Web Framework

## Status
Accepted

## Context
We needed to select a web framework for the backend API that would support:
- High performance and async capabilities
- Automatic API documentation (OpenAPI/Swagger)
- Data validation and serialization
- Dependency injection
- Easy testing and maintenance
- Modern Python features (type hints, async/await)

Several options were considered:
- Django REST Framework (mature but heavier, less async-native)
- Flask (lightweight but requires many extensions for features we need)
- FastAPI (modern, async-first, built on Starlette and Pydantic)
- Falcon (high performance but less batteries-included)

## Decision
Selected FastAPI as the web framework because it provides:
- Native async/await support for high concurrency
- Automatic OpenAPI 3.0 documentation generation
- Built-in data validation, serialization, and documentation via Pydantic
- Dependency injection system for clean architecture
- High performance (comparable to NodeJS and Go)
- Excellent developer experience with automatic docs
- Minimal boilerplate for common web API patterns

## Consequences
### Positive
- Automatic interactive API documentation at `/docs`
- Reduced boilerplate for data validation and serialization
- Excellent performance for I/O bound operations (LLM calls, DB queries)
- Strong typing reduces runtime errors
- Easy testing with TestClient
- Growing ecosystem and community

### Negative
- Newer framework than Django/Flask (less historical precedent)
- Learning curve for team members unfamiliar with it
- Fewer third-party plugins compared to Django ecosystem

### Neutral
- Requires Python 3.7+ (we already target 3.8+)
- Uses Pydantic for data modeling (which we would likely adopt anyway)

## Related Documents
- [API.md](./API.md) - API contract references
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture overview
- Source code in `app/main.py` and `app/api/` directory
````

---

*Last Updated: 2024-01-22*
*To add new decisions, create a file in the decisions/ directory following the naming convention and update this index.*