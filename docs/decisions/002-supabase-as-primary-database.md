# 002 - Use Supabase as Primary Database

## Status
Accepted

## Context
We needed to select a database solution for storing book metadata, chapter content, user information, and system configuration. Requirements included:
- Relational data model for books, chapters, and relationships
- JSONB support for flexible outline storage
- Row Level Security (RLS) for multi-tenant isolation
- Built-in authentication and authorization
- Real-time capabilities (potential future use)
- Easy deployment and maintenance
- Scalability for expected load
- Cost-effectiveness for startup/mvp phase

Options evaluated:
- Self-hosted PostgreSQL (full control but ops overhead)
- Amazon RDS PostgreSQL (managed but more complex setup)
- Google Cloud SQL (similar to RDS)
- Supabase (open-source Firebase alternative with PostgreSQL)
- MongoDB (document-oriented but less ideal for relational data)
- SQLite (simple but not suitable for production scaling)

## Decision
Selected Supabase as the primary database because it provides:
- Hosted PostgreSQL with managed backups, updates, and monitoring
- Built-in authentication service (GoTrue) that integrates well with our needs
- Automatic API generation (PostgREST) though we use direct client access
- Row Level Security (RLS) built-in and easy to configure
- Real-time subscriptions via WebSocket (available for future enhancement)
- Generous free tier for development and early staging
- Open source core allowing self-hosting if needed later
- Excellent developer experience with dashboard and SQL editor
- JWT compatibility with our authentication strategy
- Storage service for potential future file storage needs

## Consequences
### Positive
- Reduced operational overhead compared to self-hosted solution
- Built-in auth reduces custom authentication implementation
- RLS simplifies multi-tenant data isolation
- Easy to get started with minimal configuration
- SQL editor and dashboard for administration
- Automatic scalability within plan limits
- Strong community and documentation

### Negative
- Vendor lock-in to Supabase-specific features (though core is PostgreSQL)
- Less control over exact PostgreSQL version and extensions
- Potential cost increases at scale (manageable with monitoring)
- Dependence on Supabase service availability and uptime

### Neutral
- Still fundamentally PostgreSQL, so skills transferable
- Can migrate to self-hosted PostgreSQL if needed (with effort)
- Uses standard PostgreSQL features we would likely adopt anyway

## Related Documents
- [SCHEMA.md](../SCHEMA.md) - Database schema documentation
- Source code in `app/services/db_service.py`
- SQL migration files in `sql/` directory
- Authentication implementation in `app/services/user_service.py`