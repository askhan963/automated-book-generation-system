from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from typing import List, Optional
from uuid import UUID

from app.modules.projects.schemas import (
    ProjectCreateRequest,
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
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserResponse
from app.modules.auth.service import get_project_id_by_api_key

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


async def get_current_user_or_project(
    auth: Optional[str] = Header(None, alias="Authorization"),
    api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    """
    Resolve the current identity:
    - Bearer JWT → user
    - x-api-key → project key
    """
    if auth and auth.startswith("Bearer "):
        from app.modules.auth.dependencies import decode_via_token

        user = await decode_via_token(auth.split(" ", 1)[1])
        return {"identity": "user", "user": user}
    if api_key:
        project_id = get_project_id_by_api_key(api_key)
        if project_id:
            return {"identity": "project-key", "project_id": project_id}
        raise HTTPException(status_code=401, detail="Invalid API key")
    raise HTTPException(status_code=401, detail="Authentication required")


async def require_owner(
    project_id: UUID = Path(..., description="UUID of the project"),
    dep: dict = Depends(get_current_user_or_project),
):
    """Ensure the caller may act on project_id."""
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if dep["identity"] == "user":
        if str(proj["owner_id"]) != str(dep["user"].id) and dep["user"].role.value != "admin":
            raise HTTPException(status_code=403, detail="Not the owner of this project")
    elif dep["identity"] == "project-key":
        if str(dep["project_id"]) != str(project_id):
            raise HTTPException(status_code=403, detail="API key does not match project")
    return project_id


@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project for the authenticated user",
)
async def create_project_endpoint(
    payload: ProjectCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    new_proj = create_project(
        name=payload.name,
        description=payload.description,
        owner_id=current_user.id,
    )
    return new_proj


@router.get(
    "/",
    response_model=List[ProjectResponse],
    summary="List projects owned by the authenticated user",
)
async def list_projects_endpoint(
    current_user: UserResponse = Depends(get_current_user),
):
    return list_projects_by_user(current_user.id)


@router.get(
    "/{proj_id}",
    response_model=ProjectResponse,
    summary="Get a project by its UUID",
)
async def get_project_endpoint(
    proj_id: UUID = Path(..., description="Project UUID"),
    _: UUID = Depends(require_owner),
):
    proj = get_project(proj_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@router.patch(
    "/{proj_id}",
    response_model=ProjectResponse,
    summary="Update name/description of a project you own",
)
async def update_project_endpoint(
    payload: ProjectUpdateRequest,
    proj_id: UUID = Path(..., description="Project UUID"),
    _: UUID = Depends(require_owner),
):
    updated = update_project(
        project_id=proj_id,
        name=payload.name,
        description=payload.description,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")
    return updated


@router.delete(
    "/{proj_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project (and its API keys, quota rows, etc.)",
)
async def delete_project_endpoint(
    proj_id: UUID = Path(..., description="Project UUID"),
    _: UUID = Depends(require_owner),
):
    delete_project(proj_id)
    return None


@router.post(
    "/{proj_id}/keys",
    response_model=ApiKeyCreateResponse,
    summary="Generate a new API key for the project",
)
async def create_api_key_endpoint(
    proj_id: UUID = Path(..., description="Project UUID"),
    _: UUID = Depends(require_owner),
):
    import secrets

    raw = secrets.token_urlsafe(32)
    key_info = create_api_key(
        project_id=proj_id,
        raw_key=raw,
        expiration=None,
    )
    return ApiKeyCreateResponse(
        api_key=raw,
        key_id=key_info["id"],
        expires_at=key_info.get("expires_at"),
    )


@router.get(
    "/{proj_id}/keys",
    response_model=ApiKeyListResponse,
    summary="List API keys belonging to this project",
)
async def list_api_keys_endpoint(
    proj_id: UUID = Path(..., description="Project UUID"),
    _: UUID = Depends(require_owner),
):
    from app.services.db_service import _run, get_supabase

    def _fetch():
        result = (
            get_supabase()
            .table("api_keys")
            .select("id, created_at, expires_at, revoked")
            .eq("project_id", str(proj_id))
            .execute()
        )
        return result.data or []

    keys = _run(_fetch)
    return ApiKeyListResponse(keys=keys)


@router.patch(
    "/{proj_id}/keys/{key_id}",
    response_model=ApiKeyItemResponse,
    summary="Revoke or update an existing API key",
)
async def manage_api_key_endpoint(
    proj_id: UUID = Path(..., description="Project UUID"),
    key_id: UUID = Path(..., description="API key UUID"),
    revoke: bool = Query(False, description="True → mark revoked"),
    expires_at: Optional[datetime] = Query(None, description="New expiration"),
    _: UUID = Depends(require_owner),
):
    from app.services.db_service import _run, get_supabase

    def _update():
        payload: dict = {}
        if revoke is True:
            payload["revoked"] = True
        if expires_at is not None:
            payload["expires_at"] = expires_at.isoformat()
        if not payload:
            raise HTTPException(status_code=400, detail="No updates provided")
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
        id=updated["id"],
        created_at=updated["created_at"],
        expires_at=updated.get("expires_at"),
        revoked=updated.get("revoked", False),
    )


@router.delete(
    "/{proj_id}/keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an API key permanently",
)
async def delete_api_key_endpoint(
    proj_id: UUID = Path(...),
    key_id: UUID = Path(...),
    _: UUID = Depends(require_owner),
):
    from app.services.db_service import _run, get_supabase

    def _delete():
        get_supabase().table("api_keys").delete().eq(
            "project_id", str(proj_id)
        ).eq("id", str(key_id)).execute()

    _run(_delete)
    return None
