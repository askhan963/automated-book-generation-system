from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from enum import Enum

class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: Role
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, d: dict) -> "UserResponse":
        d["role"] = Role(d["role"])
        return cls(**d)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int