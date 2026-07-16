from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from typing import List, Optional
from uuid import UUID

from pydantic import Field

from app.modules.projects.schemas import (
    ProjectCreateResponse,
    ProjectResponse,
    ProjectUpdateRequest,
    ApiKeyCreateResponse,
    ApiKeyItemResponse,
    ApiKeyListResponse,
)
from app.modules.projects.service import (
    create_project,
    get_project,
    list_projects_by_user,
    update_project,
    delete_project,
    create_api_key,
)
from app.modules.auth.service import (
    get_current_user,
    get_project_id_by_api_key,
    ACCESS_EXPIRE_MINUTES,
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

# ----------------------------------------------------------------------
# Dependency: verify current user (JWT or API-key based)
# ----------------------------------------------------------------------
async def get_current_user_or_project(
    auth: Optional[str] = Header(None, alias="Authorization"),
    api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    """
    Resolve the current identity:
    - If a Bearer JWT is supplied, return the associated ``UserResponse``.
    - If an ``x-api-key`` header is supplied, return a dict with the caller’s
      ``project_id`` (the key belongs to that project).
    Raises 401 if neither works or the caller is not authenticated.
    """
    # 1️⃣ JWT path
    if auth and auth.startswith("Bearer "):
        user = await get_current_user(auth.split(" ", 1)[1])
        return {"identity": "user", "user": user}
    # 2️⃣ API‑key path
    if api_key:
        project_id = get_project_id_by_api_key(api_key)
        if project_id:
            return {"identity": "project-key", "project_id": project_id}
        raise HTTPException(status_code=401, detail="Invalid API key")
    raise HTTPException(status_code=401, detail="Authentication required")


# ----------------------------------------------------------------------
# Helper: confirm caller owns the target project
# ----------------------------------------------------------------------
async def require_owner(
    project_id: UUID = Path(..., description="UUID of the project"),
    dep: dict = Depends(get_current_user_or_project),
):
    """
    Ensure the caller is allowed to act on *project_id*:
    - Admins can act on any project.
    - Normal users can act only on projects they own.
    """
    proj = await get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    # If caller is a normal user (not an admin) verify ownership
    if dep["identity"] == "user":
        if proj["owner_id"] != dep["user"].id:
            raise HTTPException(status_code=403, detail="Not the owner of this project")
    return project_id


# ----------------------------------------------------------------------
# 1️⃣ Create a new project
# ----------------------------------------------------------------------
@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project for the authenticated user",
)
async def create_project_endpoint(
    payload: ProjectCreateResponse,
    user_proj: dict = Depends(get_current_user_or_project),
):
    """
    Create a new project for the caller.
    - The `owner_id` is automatically set to the caller’s user record.
    - Returns the full project record (incl. timestamps).
    """
    # Only allow JWT-authenticated users to create projects (not API keys)
    if user_proj["identity"] != "user":
        raise HTTPException(status_code=403, detail="Only users can create projects")

    user = user_proj["user"]
    new_proj = create_project(
        name=payload.name,
        description=payload.description,
        owner_id=user.id,
    )
    return new_proj


# ----------------------------------------------------------------------
# 2️⃣ Retrieve a project
# ----------------------------------------------------------------------
@router.get(
    "/{proj_id}",
    response_model=ProjectResponse,
    summary="Get a project by its UUID",
)
async def get_project_endpoint(
    proj_id: UUID = Path(..., description="Project UUID"),
    proj: dict = Depends(require_owner),
):
    return await get_project(proj_id)


# ----------------------------------------------------------------------
# 3️⃣ Update a project
# ----------------------------------------------------------------------
@router.patch(
    "/{proj_id}",
    response_model=ProjectResponse,
    summary="Update name/description of a project you own",
)
async def update_project_endpoint(
    payload: ProjectUpdateRequest,
    proj_id: UUID = Path(..., description="Project UUID"),
    proj: dict = Depends(require_owner),
):
    return await update_project(
        project_id=proj_id,
        name=payload.name,
        description=payload.description,
    )


# ----------------------------------------------------------------------
# 4️⃣ Delete a project
# ----------------------------------------------------------------------
@router.delete(
    "/{proj_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project (and its API keys, quota rows, etc.)",
)
async def delete_project_endpoint(
    proj_id: UUID = Path(..., description="Project UUID"),
    proj: dict = Depends(require_owner),
):
    await delete_project(proj_id)
    return None


# ----------------------------------------------------------------------
# 5️⃣ API‑Key management under a project
# ----------------------------------------------------------------------
@router.post(
    "/{proj_id}/keys",
    responses={
        200: {"model": ApiKeyCreateResponse, "description": "Create a new API key"},
        403: {"description": "Not the owner"},
    },
    summary="Generate a new API key for the project",
)
async def create_api_key_endpoint(
    proj_id: UUID = Path(..., description="Project UUID"),
    user_proj: dict = Depends(get_current_user_or_project),
):
    """
    Server generates a random secret, stores its SHA-256 hash, and returns the
    **raw** key to the caller (shown only once).  The key is tied to the
    originating project and can be revoked later.
    """
    # Create a random secret (32-byte base64)
    import secrets
    raw = secrets.token_urlsafe(32)
    expires_at = None  # No expiration by default; caller can request one
    key_info = create_api_key(
        project_id=proj_id,
        raw_key=raw,
        expiration=expires_at,
    )
    return ApiKeyCreateResponse(api_key=raw, key_id=key_info["key_id"], expires_at=key_info["expires_at"], revoked=key_info["revoked"])


@router.get(
    "/{proj_id}/keys",
    response_model=ApiKeyListResponse,
    summary="List API keys belonging to this project",
)
async def list_api_keys_endpoint(
    proj_id: UUID = Path(..., description="Project UUID"),
    user_proj: dict = Depends(require_owner),
):
    from app.services.db_service import _run, get_supabase
    def _fetch():
        result = (
            get_supabase()
            .table("api_keys")
            .select("id", "created_at", "expires_at", "revoked")
            .eq("project_id", str(proj_id))
            .execute()
        )
        return result.data or []
    keys = _run(_fetch)
    return ApiKeyListResponse(keys=keys)


@router.patch(
    "/{proj_id}/keys/{key_id}",
    responses={
        200: {"model": ApiKeyItemResponse, "description": "Toggle revocation or extend TTL"},
        403: {"description": "Not authorized"},
        404: {"description": "Key not found"},
    },
    summary="Revoke or update an existing API key",
)
async def manage_api_key_endpoint(
    proj_id: UUID = Path(..., description="Project UUID"),
    key_id: UUID = Path(..., description="API key UUID"),
    revoke: bool = Query(False, description="True → mark revoked; False → set new expiration"),
    expires_at: Optional[datetime] = Query(None, description="New expiration date for the key"),
    user_proj: dict = Depends(get_current_user_or_project),
):
    # Verify ownership (already ensured by `require_owner`)
    def _update():
        payload: dict = {}
        if revoke is True:
            payload["revoked"] = True
        if expires_at is not None:
            payload["expires_at"] = expires_at.isoformat()
        result = (
            get_supabase()
            .table("api_keys")
            .update(payload)
            .eq("project_id", str(proj_id))
            .eq("id", str(key_id))
            .execute()
        )
        return result.data[0] if result.data else None
    updated = _run(_update)
    if not updated:
        raise HTTPException(status_code=404, detail="API key not found")
    return ApiKeyItemResponse(
        id=key_id,
        created_at=updated[0]["created_at"],
        expires_at=updated[0].get("expires_at"),
        revoked=updated[0].get("revoked", False),
    )


@router.delete(
    "/{proj_id}/keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an API key permanently",
)
async def delete_api_key_endpoint(
    proj_id: UUID = Path(...),
    key_id: UUID = Path(...),
    user_proj: dict = Depends(get_current_user_or_project),
):
    from app.services.db_service import _run, get_supabase
    def _delete():
        result = (
            get_supabase()
            .table("api_keys")
            .delete()
            .eq("project_id", str(proj_id))
            .eq("id", str(key_id))
            .execute()
        )
        return result
    _run(_delete)