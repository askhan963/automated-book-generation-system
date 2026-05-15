from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


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


class GenerateOutlineRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    notes: str | None = None


class GenerateChapterRequest(BaseModel):
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
