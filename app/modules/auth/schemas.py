from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime
from enum import Enum


class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: Role
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, d: dict) -> "UserResponse":
        data = dict(d)
        data["role"] = Role(data["role"])
        return cls(**data)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
