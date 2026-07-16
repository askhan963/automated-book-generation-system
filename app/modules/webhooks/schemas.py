from pydantic import BaseModel
from typing import Optional, Dict, Any
from uuid import UUID

class OutlineApprovedWebhook(BaseModel):
    book_id: UUID
    book_title: str
    outline_data: Dict[str, Any]
    approved_by: Optional[str] = None
    approval_notes: Optional[str] = None

class ChapterCompletedWebhook(BaseModel):
    book_id: UUID
    book_title: str
    chapter_number: int
    chapter_title: str
    chapter_summary: Optional[str] = None
    completed_by: Optional[str] = None