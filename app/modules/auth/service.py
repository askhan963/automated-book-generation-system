from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
import hashlib

from passlib.context import CryptContext
from jose import JWTError, jwt

from app.core.config import get_settings
from app.services.db_service import _run, get_supabase
from app.modules.auth.schemas import Role, UserResponse, TokenResponse
from fastapi import Header, HTTPException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = get_settings().jwt_secret
ALGORITHM = "HS256"
ACCESS_EXPIRE_MINUTES = get_settings().jwt_expires_minutes

# ---------- Password Utils ----------
def _truncate_password(pw: str, max_bytes: int = 72) -> str:
    """Truncate a password string to at most max_bytes when encoded as UTF-8."""
    pw_bytes = pw.encode('utf-8')
    if len(pw_bytes) <= max_bytes:
        return pw
    # truncate to max_bytes and decode, ignoring any incomplete character at the end
    return pw_bytes[:max_bytes].decode('utf-8', errors='ignore')

def hash_password(pw: str) -> str:
    pw_truncated = _truncate_password(pw)
    return pwd_context.hash(pw_truncated)

def verify_password(pw: str, hashed: str) -> bool:
    pw_truncated = _truncate_password(pw)
    return pwd_context.verify(pw_truncated, hashed)

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
def get_user_by_email(email: str) -> dict[str, Any] | None:
    def _fetch():
        result = (
            get_supabase()
            .table("users")
            .select("*")
            .eq("email", email)
            .maybe_single()
            .execute()
        )
        return result.data
    return _run(_fetch)

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

# ---------- Service Functions ----------

async def get_current_user(token: str) -> UserResponse:
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    email = payload.get("sub")
    if email is None:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    user = get_user_by_email(email)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return UserResponse.from_dict(user)


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