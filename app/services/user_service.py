from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID
import hashlib

from passlib.context import CryptContext
from jose import JWTError, jwt

from app.core.config import get_settings
from app.services.db_service import _run, get_supabase

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = get_settings().jwt_secret
ALGORITHM = "HS256"
ACCESS_EXPIRE_MINUTES = get_settings().jwt_expires_minutes

# ---------- Password Utils ----------
def hash_password(pw: str) -> str:
    return pwd_context.hash(pw)

def verify_password(pw: str, hashed: str) -> bool:
    return pwd_context.verify(pw, hashed)

# ---------- JWT Utils ----------
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

# ---------- API Key Utils ----------
def generate_api_key(raw: str, expiration: datetime | None = None):
    """Generate hashed API key and return both hash and raw key.
    Returns a dict with keys: key_hash, key, key_id, expires_at, revoked.
    """
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    key_id = UUID()
    return {
        "key_hash": key_hash,
        "key": raw,
        "key_id": key_id,
        "expires_at": expiration,
        "revoked": False
    }

def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

# ---------- Usage Tracking ----------
def record_token_usage(project_id: UUID, tokens: int) -> None:
    today = datetime.utcnow().date()
    def _upsert() -> dict[str, Any]:
        result = (
            get_supabase()
            .table("usage_quota")
            .upsert({
                "project_id": str(project_id),
                "day": today.isoformat(),
                "token_count": tokens
            }, on_conflict="project_id,day")
            .execute()
        )
        return result.data[0]
    _run(_upsert)

def get_usage_today(project_id: UUID) -> int:
    today = datetime.utcnow().date()
    def _fetch():
        result = (
            get_supabase()
            .table("usage_quota")
            .select("token_count")
            .eq("project_id", str(project_id))
            .eq("day", today.isoformat())
            .maybe_single()
            .execute()
        )
        return result.data["token_count"] if result.data else 0
    return _run(_fetch)

# ---------- DB Query Helpers ----------
def get_user_by_id(user_id: UUID) -> dict[str, Any] | None:
    def _fetch():
        result = (
            get_supabase()
            .table("users")
            .select("*")
            .eq("id", str(user_id))
            .maybe_single()
            .execute()
        )
        return result.data
    return _run(_fetch)

# ---------- Authorization Utils ----------
def get_current_user_role(user: dict) -> str:
    return user.get("role", "user")

def check_quota_limit(project_id: UUID, max_tokens: int) -> bool:
    return get_usage_today(project_id) < max_tokens

# ---------- API Key Auth for Internal Services ----------
# These functions look up projects by API key hash
# Used for Authorization in other services like AI service

def get_project_by_api_key(raw_key: str):
    key_hash = hash_api_key(raw_key)
    def _fetch():
        result = (
            get_supabase()
            .table("api_keys")
            .select("project_id")
            .eq("key_hash", key_hash)
            .eq("revoked", False)
            .gte("expires_at", datetime.utcnow())
            .execute()
        )
        return result.data[0] if result.data else None
    return _run(_fetch)

def get_project_id_by_api_key(raw_key: str):
    row = get_project_by_api_key(raw_key)
    if row:
        return UUID(row["project_id"])
    return None

# ---------- Model Definitions ----------

class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"

class UserResponse(BaseModel):
    id: UUID
    email: str
    role: Role
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "UserResponse":
        d["role"] = Role(d["role"])
        return cls(**d)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

# ---------- Service Functions ----------

def create_user(email: str, plain_password: str) -> dict[str, Any]:
    password = hash_password(plain_password)
    def _insert():
        result = (
            get_supabase()
            .table("users")
            .insert({
                "email": email,
                "password": password,
                "role": Role.USER.value,
            })
            .execute()
        )
        return result.data[0]
    return _run(_insert)

# ---------- Service Authorization Wrapper ----------

def require_auth(_func):
    def wrapper(api_key_header: str, *args, **kwargs):
        project_id = get_project_id_by_api_key(api_key_header)
        if not project_id:
            raise HTTPException(status_code=401, detail="Invalid or expired API key")
        return _func(project_id=project_id, *args, **kwargs)
    return wrapper

# ---------- Auth Dependency ----------

from fastapi import Depends, HTTPException, Header

async def get_current_user(
    authorization: str = Header(None)
) -> UserResponse:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing auth header")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_email = payload.get("sub")
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    def _fetch():
        result = (
            get_supabase()
            .table("users")
            .select("*")
            .eq("email", user_email)
            .maybe_single()
            .execute()
        )
        return result.data
    user = _run(_fetch)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse.from_dict(user)

async def get_current_user_or_api_key(
    auth: str = Header(None),
    api_key: str = Header(None, alias="x-api-key")
):
    """Try JWT first, if that fails try API key."""
    if auth and auth.startswith("Bearer "):
        return await get_current_user(auth)
    elif api_key:
        project_id = get_project_id_by_api_key(api_key)
        if project_id:
            return {"id": "internal-api-key", "project_id": project_id, "role": "project"}
    raise HTTPException(status_code=401, detail="Authentication required")

async def require_user(project_dependency: dict = Depends(get_current_user_or_api_key)):
    """Dependency that extracts the user. If using API key, project is used."""
    return project_dependency