# /feature command — build a backend feature

Read these files BEFORE writing any code:
1. docs/PROGRESS.md   — confirm this task is not already built
2. docs/SCHEMA.md     — know what tables and columns exist
3. docs/API.md        — check if relevant routes already exist
4. docs/ARCHITECTURE.md — follow the patterns there

Feature to build: $ARGUMENTS

## Build order (always follow this sequence)
1. Supabase Migration
2. Alembic migration — autogenerate + inspect before applying
3. Pydantic schemas (request + response)
4. Repository — database queries
5. Service — business logic
6. Router — HTTP handler
7. Tests — service layer (mock repo) + router layer (TestClient)
8. Verify in Swagger

## Checklist before marking done
- [ ] tell specifically which migration to run on the supabase i run my self
- [ ] docs/SCHEMA.md updated (if schema changed)
- [ ] Route added to docs/API.md
- [ ] python -m pytest passes
- [ ] ruff check . passes
- [ ] Route visible and testable in Swagger at /docs
- [ ] docs/PROGRESS.md updated — task marked done
- [ ] Tell me exact steps to manually verify this feature
