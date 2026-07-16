from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


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
    initial_notes: Optional[str] = None
    auto_approve_outline: bool = False
    genre: Optional[str] = None
    tone: Optional[str] = None
    audience: Optional[str] = None
    length: Optional[str] = None


class GenerateOutlineRequest(BaseModel):
    genre: Optional[str] = None
    tone: Optional[str] = None
    audience: Optional[str] = None
    length: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=500)
    notes: Optional[str] = None


class GenerateChapterRequest(BaseModel):
    genre: Optional[str] = None
    tone: Optional[str] = None
    audience: Optional[str] = None
    length: Optional[str] = None
    chapter_id: UUID


class BookNotesUpdate(BaseModel):
    human_notes: str
    status: StageStatus = StageStatus.APPROVED


class FinalReviewUpdate(BaseModel):
    human_notes: Optional[str] = None
    status: StageStatus = StageStatus.NO_NOTES_NEEDED


class ChapterNotesUpdate(BaseModel):
    human_notes: Optional[str] = None
    status: StageStatus = StageStatus.APPROVED


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


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
    initial_notes: Optional[str]
    outline: Optional[OutlineData | dict[str, Any]]
    outline_status: StageStatus
    final_review_notes_status: StageStatus = StageStatus.PENDING_REVIEW
    phase: BookPhase
    human_notes: Optional[str]
    genre: Optional[str] = None
    tone: Optional[str] = None
    audience: Optional[str] = None
    length: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ChapterResponse(BaseModel):
    id: UUID
    book_id: UUID
    chapter_number: int
    title: str
    content: Optional[str]
    summary: Optional[str]
    status: StageStatus
    human_notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class BookDraftResponse(BaseModel):
    book: BookResponse
    chapters: list[ChapterResponse]
    full_text: str


class MessageResponse(BaseModel):
    message: str
    book_id: Optional[UUID] = None
    chapter_id: Optional[UUID] = None


class ServiceHealth(BaseModel):
    status: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    message: str
    supabase: ServiceHealth
    openrouter: ServiceHealth