# 006 - Use JWT and API Key Authentication

## Status
Accepted
## Context
We needed to implement authentication and authorization for the Automated Book Generation System to:
- Securely identify users and their associated projects
- Protect API endpoints from unauthorized access
- Enable service-to-service communication (internal API calls)
- Support both interactive user access and automated workflows
- Provide secure token-based authentication suitable for REST APIs
- Allow for token expiration and revocation when needed
- Support role-based access control (user vs admin)
- Enable audit trails and usage tracking per user/project

Options considered:
- Session-based authentication (cookies, server-side state) - not ideal for APIs
- JWT (JSON Web Tokens) - stateless, scalable, widely adopted
- API Keys - simple, good for service-to-service and programmatic access
- OAuth 2.0 - comprehensive but complex overkill for our needs
- Basic Auth over HTTPS - simple but credentials sent with every request
- API Key + JWT hybrid - combines strengths of both approaches
- Third-party auth providers (Auth0, Firebase Auth) - introduces dependency

## Decision
Implemented a dual-authentication system:
1. **JWT Authentication** for user-facing interactions (web/mobile apps)
   - Users register/login via `/auth/register` and `/auth/login` endpoints
   - JWT issued with user ID, email, role, and expiration
   - Tokens sent via `Authorization: Bearer <token>` header
   - Role-based access control (user/admin) enforced in route dependencies
   - Token validation includes signature verification and expiration checks
   - Access token stored client-side (local storage, session storage, etc.)

2. **API Key Authentication** for service-to-service and programmatic access
   - API keys tied to specific projects (not individual users)
   - Keys generated via project management endpoints (`POST /projects/{id}/keys`)
   - Raw key shown only once at creation; stored as SHA-256 hash in database
   - Keys sent via `X-API-Key` header
   - Automatic project identification from key hash
   - Key revocation and expiration capabilities
   - Usage tracking tied to projects for quota enforcement

Both authentication methods feed into a common authorization system that:
- Verifies identity and associated project/user context
- Enforces role-based permissions (where applicable)
- Supports ownership-based access control (users can only access their own projects)
- Provides consistent user/project context to downstream services
- Logs authentication events for audit trails

## Consequences
### Positive
- JWT provides stateless scalability for user authentication
- API keys enable secure automation and integration workflows
- Dual approach supports both interactive and programmatic use cases
- Hash-based API key storage prevents key exposure if database compromised
- Key rotation and revocation capabilities enhance security
- Usage monitoring and quota enforcement possible per project
- Clear separation between user identity and project resources
- Industry-standard approaches with well-understood security properties
- Flexible enough to support future auth methods (OAuth, SSO) if needed

### Negative
- Slightly more complex than single-method authentication
- Need to manage two different authentication flows in client code
- JWT token management required client-side (storage, renewal, etc.)
- Potential for confusion between user-auth and api-key-auth contexts
- Revocation requires explicit implementation (not automatic with JWT)
- API key compromise requires key rotation (exposure window until detected)

### Neutral
- Both approaches are REST-friendly and stateless
- Follows common patterns seen in platforms like Stripe, Twilio, AWS
- Security implementations based on well-vetted libraries (python-jose, passlib, bcrypt)
- Can extend to support refresh tokens for JWT if long-lived sessions needed
- Auditing and logging capabilities apply to both auth methods

## Related Documents
- [API.md](../API.md) - Authentication endpoints (`/auth/*`) and protected routes
- Source code in `app/services/user_service.py` (auth logic, hashing, JWT)
- Source code in `app/services/db_service.py` (API key and usage tracking)
- Source code in `app/api/auth.py` (login/register endpoints)
- Source code in `app/api/projects.py` (project and API key management)
- Source code in `app/api/projects.py` (authentication dependencies)
- Source code in `app/core/config.py` (JWT and security-related settings)