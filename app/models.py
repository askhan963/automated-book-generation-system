from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

# --- StageStatus and BookPhase stay unchanged ---
class StageStatus(str, Enum):
    PENDING_NOTES = "pending_notes"
    PENDING_REVIEW = "pending_review"
    OUTLINE_REVIEW = "outline_review"
    APPROVED = "approved"
    NO_NOTES_NEEDED = "no_notes_needed"

class BookPhase(str, Enum):
    OUTLINE = "outline"
    CHAPTERS = "chapters"
    COMPLETED = "completed"


# --- Requests ---
class BookCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    initial_notes: str | None = None
    auto_approve_outline: bool = False
    genre: str | None = None
    tone: str | None = None
    audience: str | None = None
    length: str | None = None


class GenerateOutlineRequest(BaseModel):
    genre: str | None = None
    tone: str | None = None
    audience: str | None = None
    length: str | None = None
    title: str = Field(..., min_length=1, max_length=500)
    notes: str | None = None


class GenerateChapterRequest(BaseModel):
    genre: str | None = None
    tone: str | None = None
    audience: str | None = None
    length: str | None = None
    chapter_id: UUID


class BookNotesUpdate(BaseModel):
    human_notes: str
    status: StageStatus = StageStatus.APPROVED


class FinalReviewUpdate(BaseModel):
    human_notes: str | None = None
    status: StageStatus = StageStatus.NO_NOTES_NEEDED


class ChapterNotesUpdate(BaseModel):
    human_notes: str | None = None
    status: StageStatus = StageStatus.APPROVED


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class OutlineChapterItem(BaseModel):
    chapter_number: int
    title: str
    brief: str


class OutlineData(BaseModel):
    chapters: list[OutlineChapterItem]


# --- Responses ---
class BookResponse(BaseModel):
    id: UUID
    title: str
    initial_notes: str | None
    outline: OutlineData | dict[str, Any] | None
    outline_status: StageStatus
    final_review_notes_status: StageStatus = StageStatus.PENDING_REVIEW
    phase: BookPhase
    human_notes: str | None
    genre: str | None = None
    tone: str | None = None
    audience: str | None = None
    length: str | None = None
    created_at: datetime
    updated_at: datetime


class ChapterResponse(BaseModel):
    id: UUID
    book_id: UUID
    chapter_number: int
    title: str
    content: str | None
    summary: str | None
    status: StageStatus
    human_notes: str | None
    created_at: datetime
    updated_at: datetime


class BookDraftResponse(BaseModel):
    book: BookResponse
    chapters: list[ChapterResponse]
    full_text: str


class MessageResponse(BaseModel):
    message: str
    book_id: UUID | None = None
    chapter_id: UUID | None = None


class ServiceHealth(BaseModel):
    status: str
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    message: str
    supabase: ServiceHealth
    openrouter: ServiceHealth


# --- Auth & Security Models ---
from pydantic import EmailStr
from uuid import UUID
from datetime import datetime

# User models
class UserCreateResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer", "api_key"] = "bearer"
    expires_in: int
    scope: str | None = None


# Project models
class ProjectCreateResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    owner_id: UUID
    created_at: datetime
    updated_at: datetime

class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    owner_id: UUID
    created_at: datetime
    updated_at: datetime


# API Key responses
class ApiKeyItemResponse(BaseModel):
    id: UUID
    created_at: datetime
    expires_at: datetime | None
    revoked: bool


class ApiKeyListResponse(BaseModel):
    keys: list[ApiKeyItemResponse]

class ApiKeyCreateResponse(BaseModel):
    api_key: str
    key_id: UUID
    expires_at: datetime | None


# --- Template Models ---
class TemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    template_json: dict[str, Any]  # Should match OutlineData structure
    category: str | None = None
    is_public: bool = True
    created_by: UUID | None = None


class TemplateResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    template_json: dict[str, Any]
    category: str | None
    is_public: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class TemplateUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    template_json: dict[str, Any] | None = None
    category: str | None = None
    is_public: bool | None = None


class TemplateListResponse(BaseModel):
    templates: list[TemplateResponse]
