# Automated Book Generation System Backend — Database Schema Reference

This document describes the database schema used by the Automated Book Generation System backend, implemented in PostgreSQL via Supabase.

## Overview

The schema is designed to support:
- Book and chapter lifecycle management with human-in-the-loop review gates
- User and project management with API key-based access
- Template storage for reusable outline structures
- Usage tracking and analytics
- Extensible metadata for writing style and configuration

## Custom Types

### StageStatus
```sql
CREATE TYPE stage_status AS ENUM (
    'pending_notes',
    'pending_review',
    'outline_review',
    'approved',
    'no_notes_needed'
);
```
Tracks the review status of books and chapters at various stages of the generation process.

### BookPhase
```sql
CREATE TYPE book_phase AS ENUM (
    'outline',
    'chapters',
    'completed'
);
```
Indicates the current phase of a book in its lifecycle.

## Tables

### books
Stores core book metadata and generation state.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique identifier for the book |
| title | TEXT | NOT NULL | Title of the book |
| initial_notes | TEXT | | Initial notes/provided by user for outline generation |
| outline | JSONB | | Generated outline structure (array of chapters with numbers, titles, briefs) |
| outline_status | stage_status | NOT NULL DEFAULT 'pending_review' | Review status of the book outline |
| final_review_notes_status | stage_status | NOT NULL DEFAULT 'pending_review' | Review status for final book clearance |
| phase | book_phase | NOT NULL DEFAULT 'outline' | Current lifecycle phase of the book |
| human_notes | TEXT | | Consolidated feedback from reviewers |
| genre | TEXT | | Writing genre for style tracking and generation |
| tone | TEXT | | Writing tone for style tracking and generation |
| audience | TEXT | | Target audience for style tracking and generation |
| length | TEXT | | Desired book length for style tracking and generation |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Last update timestamp (auto-updated via trigger) |

**Indexes:**
- Implicit primary key index on `id`

**Triggers:**
- `books_updated_at`: BEFORE UPDATE trigger to automatically set `updated_at = now()`

### chapters
Stores individual chapter content, summaries, and review status.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique identifier for the chapter |
| book_id | UUID | NOT NULL, REFERENCES books(id) ON DELETE CASCADE | Foreign key to parent book |
| chapter_number | INT | NOT NULL | Sequential chapter number within the book |
| title | TEXT | NOT NULL | Chapter title |
| content | TEXT | | Generated chapter content (generated during chapter creation phase) |
| summary | TEXT | | AI-generated summary (exactly 3 sentences for context chaining) |
| status | stage_status | NOT NULL DEFAULT 'pending_review' | Current review status of the chapter |
| human_notes | TEXT | | Reviewer feedback and revision requests |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Last update timestamp (auto-updated via trigger) |

**Constraints:**
- UNIQUE (`book_id`, `chapter_number`) - prevents duplicate chapter numbers

**Indexes:**
- `idx_chapters_book_id` - indexes chapters by book for efficient lookup
- `idx_chapters_book_number` - composite index for book_id + chapter_number queries

**Triggers:**
- `chapters_updated_at`: BEFORE UPDATE trigger to automatically set `updated_at = now()`

### outline_templates
Stores reusable outline structures for books.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique identifier for the template |
| name | TEXT | NOT NULL | Human-readable template name |
| description | TEXT | | Detailed description of template use case |
| template_json | JSONB | NOT NULL | Outline structure matching `books.outline` format |
| category | TEXT | | Template classification (e.g., 'fiction', 'academic', 'technical') |
| is_public | BOOLEAN | DEFAULT TRUE | Whether template is available to all users |
| created_by | UUID | | Reference to user who created the template (nullable) |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Last update timestamp (auto-updated via trigger) |

**Indexes:**
- `idx_outline_templates_category` - indexes templates by category for filtering
- `idx_outline_templates_public` - indexes public templates for efficient public template listing

**Triggers:**
- `outline_templates_updated_at`: BEFORE UPDATE trigger to automatically set `updated_at = now()`

### projects
Stores user-owned projects that contain books and API keys.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique identifier for the project |
| owner_id | UUID | NOT NULL | Foreign key to user who owns the project |
| name | TEXT | NOT NULL | Project name |
| description | TEXT | | Project description |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Last update timestamp (auto-updated via trigger) |

**Indexes:**
- Implicit primary key index on `id`
- Index on `owner_id` for efficient user project listing

**Triggers:**
- Standard updated_at trigger (implementation varies)

### users
Stores user account information for authentication.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique identifier for the user |
| email | TEXT | NOT NULL, UNIQUE | User email address (used for login) |
| password | TEXT | NOT NULL | bcrypt-hashed password (never stored plaintext) |
| role | TEXT | NOT NULL DEFAULT 'user' | User role ('user' or 'admin') |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Last update timestamp (auto-updated via trigger) |

**Indexes:**
- Implicit primary key index on `id`
- Unique index on `email` for login lookups

**Triggers:**
- Standard updated_at trigger (implementation varies)

### api_keys
Stores hashed API keys for project-level authentication.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique identifier for the API key record |
| project_id | UUID | NOT NULL, REFERENCES projects(id) ON DELETE CASCADE | Foreign key to owning project |
| key_hash | TEXT | NOT NULL | SHA-256 hash of the API key (plaintext never stored) |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Creation timestamp |
| expires_at | TIMESTAMPTZ | | Optional expiration timestamp (NULL = no expiration) |
| revoked | BOOLEAN | NOT NULL DEFAULT FALSE | Whether the key has been revoked |

**Indexes:**
- Implicit primary key index on `id`
- Index on `project_id` for efficient project key listing
- Index on `key_hash` for fast key lookup during authentication
- Composite index on (`project_id`, `revoked`) for active key queries

### usage_quota
Tracks daily token consumption per project for rate limiting and analytics.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique identifier for the quota record |
| project_id | UUID | NOT NULL, REFERENCES projects(id) ON DELETE CASCADE | Foreign key to owning project |
| day | DATE | NOT NULL | Date of usage (YYYY-MM-DD format) |
| token_count | INTEGER | NOT NULL DEFAULT 0 | Number of tokens consumed on this day |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Last update timestamp (auto-updated via trigger) |

**Constraints:**
- UNIQUE (`project_id`, `day`) - ensures one record per project per day

**Indexes:**
- Implicit primary key index on `id`
- Index on `project_id` for efficient project quota lookup
- Index on `day` for time-based queries and analytics

## Triggers

All main tables (`books`, `chapters`, `outline_templates`, `projects`, `users`, `api_keys`, `usage_quota`) have BEFORE UPDATE triggers that automatically set the `updated_at` column to `now()` on each modification.

## Row Level Security (RLS)

RLS is enabled on all tables with permissive policies for backend API access:

### books
```sql
ALTER TABLE books ENABLE ROW LEVEL SECURITY;
CREATE POLICY "books_api_all" ON books FOR ALL USING (true) WITH CHECK (true);
```

### chapters
```sql
ALTER TABLE chapters ENABLE ROW LEVEL SECURITY;
CREATE POLICY "chapters_api_all" ON chapters FOR ALL USING (true) WITH CHECK (true);
```

### outline_templates
```sql
ALTER TABLE outline_templates ENABLE ROW LEVEL SECURITY;
CREATE POLICY "outline_templates_api_all" ON outline_templates FOR ALL USING (true) WITH CHECK (true);
```

These policies allow full access via the Supabase client (appropriate for a backend-only exposure where authentication is handled at the application level). For frontend-exposed environments, more restrictive policies would be implemented.

## Relationships

```
users 1---* projects
projects 1---* books
books 1---* chapters
projects 1---* api_keys
projects 1---* usage_quota
users 0---* outline_templates (via created_by)
```

## Indexes Summary

### Performance Indexes
- `idx_chapters_book_id` - speeds up chapter retrieval by book
- `idx_chapters_book_number` - speeds up chapter number lookups within books
- `idx_outline_templates_category` - speeds up template filtering by category
- `idx_outline_templates_public` - speeds up public template listing

### Constraint Enforcement Indexes
- Primary keys on all tables (implicit)
- Unique email index on users table
- Unique project_id/day index on usage_quota table
- Unique book_id/chapter_number index on chapters table

### Lookup Optimization Indexes
- key_hash index on api_keys table for authentication
- project_id indexes on api_keys and usage_quota tables

## Extensibility Points

The schema is designed to accommodate future enhancements:

1. **Additional Metadata**: New columns can be added to any table for extended attributes
2. **New Entity Types**: Additional tables can be introduced for features like:
   - Comments and discussion threads
   - Version history and diffs
   - Notification templates
   - Integration webhooks
   - Audit trails
3. **Enum Extensions**: New values can be added to StageStatus or BookPhase enums
4. **JSONB Expansion**: The outline and template_json fields can accommodate evolving structures
5. **Partitioning**: usage_quota table could be partitioned by date for large-scale analytics
6. **Full-text Search**: Specialized indexes could be added for content search capabilities

## Security Considerations

1. **Password Storage**: Passwords are bcrypt hashed using industry-standard cost factors
2. **API Key Security**: API keys are stored as SHA-256 hashes; plaintext keys are never persisted
3. **RLS Protection**: While currently permissive for backend use, RLS policies provide foundation for stricter controls
4. **Injection Safety**: All database access uses parameterized queries via Supabase client, preventing SQL injection
5. **Privacy Compliance**: Personal data (email, name) is minimized and secured appropriately

## Maintenance

### Backups
Managed by Supabase infrastructure with point-in-time recovery options.

### Migrations
Schema changes managed through SQL migration files in the `sql/` directory:
- Initial schema: `sql/schema.sql`
- Analytics fields: `sql/migration_add_analytics_fields_to_books.sql`
- Template storage: `sql/migration_add_template_storage.sql`
- RLS policies: `sql/rls_policies.sql` and `sql/rls_policies_outline_templates.sql`
- Additional migrations as features evolve

### Monitoring
- Connection pooling and usage metrics provided by Supabase
- Query performance monitoring available in Supabase dashboard
- Custom logging and metrics available through application instrumentation

## Diagrams

### Entity Relationship Diagram (Text Representation)
```
users
  │
  ├── 1
  │
projects ← 0―* outline_templates (via created_by)
  │
  ├── 1
  │
books ← 0―* chapters
  │
  ├── 1
  │
api_keys
  │
  ├── 1
  │
usage_quota
```

### Data Flow Example (Book Creation)
1. User creates book → INSERT into `books` with `outline_status = 'pending_review'`
2. AI generates outline → UPDATE `books` set `outline = <JSONB>`, `outline_status` based on config
3. User approves outline → UPDATE `books` set `outline_status = 'approved/no_notes_needed'`, `phase = 'chapters'`
4. Chapter generation loop:
   - Find next ungenerated chapter → Query `books.outline` vs `chapters` where `book_id = ?`
   - Create chapter stub → INSERT into `chapters` with initial status
   - Generate content → UPDATE `chapters` set `content`, `summary`, `status`
   - Repeat until all chapters generated
5. Final review clearance → UPDATE `books` set `final_review_notes_status = 'no_notes_needed'`, `phase = 'completed'`
6. Export eligibility → Check `final_review_notes_status = 'no_notes_needed'` before allowing compilation