from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.models import (
    BookResponse,
    ChapterResponse,
    GenerateChapterRequest,
    GenerateOutlineRequest,
    OutlineData,
    StageStatus,
)
from app.services import ai_service, db_service

router = APIRouter(prefix="/api/v1", tags=["generation"])

GENERATABLE_STATUSES = {
    StageStatus.APPROVED.value,
    StageStatus.NO_NOTES_NEEDED.value,
}

BLOCKING_STATUSES = {
    StageStatus.PENDING_REVIEW.value,
    StageStatus.PENDING_NOTES.value,
    "pending",  # alias requested in spec
}


@router.post("/generate-outline", response_model=BookResponse)
def generate_outline(payload: GenerateOutlineRequest):
    """Generate an outline from title/notes and persist to Supabase."""
    try:
        outline = ai_service.generate_outline(
            title=payload.title,
            initial_notes=payload.notes,
            genre=payload.genre,
            tone=payload.tone,
            audience=payload.audience,
            length=payload.length
        )
        book = db_service.create_book_with_outline(
            title=payload.title,
            notes=payload.notes,
            outline=outline,
            outline_status=StageStatus.OUTLINE_REVIEW,
            genre=payload.genre,
            tone=payload.tone,
            audience=payload.audience,
            length=payload.length,
        )
        return BookResponse.model_validate(book)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Outline generation failed: {exc}",
        ) from exc


@router.post("/generate-chapter", response_model=ChapterResponse)
def generate_chapter(payload: GenerateChapterRequest):
    """
    Generate chapter prose and summary when human gating allows it.
    Requires chapter status of approved or no_notes_needed.
    """
    chapter = db_service.get_chapter(payload.chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    status = chapter.get("status", "")
    if status in BLOCKING_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Waiting for human review",
        )
    if status not in GENERATABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Chapter not cleared for generation. Current status: {status}",
        )

    book = db_service.get_book(UUID(chapter["book_id"]))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if not book.get("outline"):
        raise HTTPException(status_code=400, detail="Book has no outline")

    outline = OutlineData.model_validate(book["outline"])
    chapter_outline = next(
        (c for c in outline.chapters if c.chapter_number == chapter["chapter_number"]),
        None,
    )
    if not chapter_outline:
        raise HTTPException(status_code=400, detail="Chapter not found in book outline")

    book_id = UUID(book["id"])
    prior_summaries = db_service.get_previous_chapter_summaries_before(
        book_id,
        chapter["chapter_number"],
    )

    content = ai_service.generate_chapter(
        book["title"],
        chapter_outline,
        prior_summaries,
        chapter.get("human_notes"),
    )
    summary = ai_service.summarize_chapter(content)

    settings = get_settings()
    new_status = (
        StageStatus.PENDING_REVIEW
        if settings.require_human_review
        else StageStatus.NO_NOTES_NEEDED
    )

    updated = db_service.update_chapter(
        payload.chapter_id,
        content=content,
        summary=summary,
        status=new_status.value,
    )
    return ChapterResponse.model_validate(updated)
