from fastapi import HTTPException
from postgrest.exceptions import APIError

try:
    import httpcore
except ImportError:  # pragma: no cover
    httpcore = None

import httpx


def _is_connection_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.ConnectError):
        return True
    if httpcore is not None and isinstance(exc, httpcore.ConnectError):
        return True
    message = str(exc).lower()
    return "no address associated with hostname" in message or "name or service not known" in message


def raise_http_from_supabase(exc: Exception) -> None:
    """Map Supabase/PostgREST/network errors to actionable HTTP responses."""
    if isinstance(exc, HTTPException):
        raise exc

    if _is_connection_error(exc):
        raise HTTPException(
            status_code=503,
            detail=(
                "Cannot reach Supabase. Check SUPABASE_URL in .env, then restart Docker "
                "(docker compose up --build -d). If the URL is correct, retry — Docker DNS "
                "can fail intermittently."
            ),
        ) from exc

    if isinstance(exc, APIError):
        code = exc.code or ""
        message = exc.message or str(exc)

        if code == "42501" or "row-level security" in message.lower():
            raise HTTPException(
                status_code=403,
                detail=(
                    "Supabase row-level security blocked this operation. "
                    "Run sql/rls_policies.sql in the SQL Editor, or set SUPABASE_KEY "
                    "to your project's service_role secret (Settings → API)."
                ),
            ) from exc

        if code == "PGRST205" or "could not find the table" in message.lower():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Database tables missing. Run sql/schema.sql in Supabase SQL Editor."
                ),
            ) from exc

        if "invalid input value for enum" in message.lower():
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Database enum mismatch: {message}. "
                    "Run sql/migration_add_outline_review.sql and "
                    "sql/migration_add_final_review_status.sql."
                ),
            ) from exc

        raise HTTPException(status_code=502, detail=f"Supabase error: {message}") from exc

    raise HTTPException(status_code=500, detail=str(exc)) from exc
