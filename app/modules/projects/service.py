from datetime import datetime
from uuid import UUID
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.services.db_service import _run, get_supabase
from app.modules.auth.schemas import Role, UserResponse

def _upsert_project(
    project_id: Optional[UUID],
    *,
    name: str,
    description: str | None,
    owner_id: UUID,
) -> Dict[str, Any]:
    payload = {
        "name": name,
        "description": description,
        "owner_id": str(owner_id),
        "updated_at": datetime.utcnow().isoformat(),
    }
    if project_id:
        payload["id"] = str(project_id)

    def _upsert() -> Dict[str, Any]:
        result = (
            get_supabase()
            .table("projects")
            .upsert(payload, on_conflict="id")
            .execute()
        )
        return result.data[0]

    return _run(_upsert)


def create_project(
    name: str,
    description: str | None,
    owner_id: UUID,
) -> Dict[str, Any]:
    return _upsert_project(
        None, name=name, description=description, owner_id=owner_id
    )


def get_project(project_id: UUID) -> Dict[str, Any]:
    def _fetch() -> Dict[str, Any]:
        result = (
            get_supabase()
            .table("projects")
            .select("*")
            .eq("id", str(project_id))
            .maybe_single()
            .execute()
        )
        return result.data
    return _run(_fetch)


def list_projects_by_user(user_id: UUID) -> List[Dict[str, Any]]:
    def _fetch() -> List[Dict[str, Any]]:
        result = (
            get_supabase()
            .table("projects")
            .select("*")
            .eq("owner_id", str(user_id))
            .execute()
        )
        return result.data or []
    return _run(_fetch)


def update_project(
    project_id: UUID,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    payload["updated_at"] = datetime.utcnow().isoformat()

    def _update() -> Dict[str, Any]:
        result = (
            get_supabase()
            .table("projects")
            .update(payload)
            .eq("id", str(project_id))
            .execute()
        )
        return result.data[0] if result.data else None

    return _run(_update)


def delete_project(project_id: UUID) -> None:
    def _delete() -> None:
        result = (
            get_supabase()
            .table("projects")
            .delete()
            .eq("id", str(project_id))
            .execute()
        )
        # Cascade delete of related api_keys, usage_quota automatically via foreign key
    _run(_delete)


def create_api_key(
    project_id: UUID,
    raw_key: str,
    expiration: datetime | None = None,
) -> Dict[str, Any]:
    from hashlib import sha256

    key_hash = sha256(raw_key.encode()).hexdigest()

    def _insert() -> Dict[str, Any]:
        result = (
            get_supabase()
            .table("api_keys")
            .insert({
                "project_id": str(project_id),
                "key_hash": key_hash,
                "expires_at": expiration.isoformat() if expiration else None,
                "revoked": False,
            })
            .execute()
        )
        return result.data[0]

    return _run(_insert)