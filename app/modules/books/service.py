"""
Business logic layer for books module.
Orchestrates repositories, AI service, export services, and webhooks.
"""
from uuid import UUID
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import HTTPException

from app.modules.books.repository import (
    create_book,
    get_book,
    list_books,
    update_book,
    create_book_with_outline,
    save_outline,
    create_chapter_stub,
    get_chapter,
    get_chapters_for_book,
    get_previous_chapter_summaries,
    get_previous_chapter_summaries_before,
    update_chapter,
    count_chapters,
    get_next_outline_chapter,
)
from app.modules.books.schemas import (
    BookResponse,
    ChapterResponse,
    BookDraftResponse,
    BookCreateRequest,
    BookNotesUpdate,
    ChapterNotesUpdate,
    FinalReviewUpdate,
    OutlineData,
    StageStatus,
    BookPhase,
)
from app.services import ai_service, db_service, export_service
from app.services.supabase_errors import raise_http_from_supabase
import logging

logger = logging.getLogger(__name__)


def create_book_and_outline(
    title: str,
    initial_notes: Optional[str] = None,
    genre: Optional[str] = None,
    tone: Optional[str] = None,
    audience: Optional[str] = None,
    length: Optional[str] = None,
    auto_approve_outline: bool = False,
) -> Dict[str, Any]:
    """Create a book and generate/save its outline."""
    try:
        # Create book record
        book = create_book(
            title=title,
            initial_notes=initial_notes,
        )

        # Generate outline via AI service
        outline = ai_service.generate_outline(
            title=title,
            initial_notes=initial_notes,
            genre=genre,
            tone=tone,
            audience=audience,
            length=length,
        )

        # Determine outline status based on settings
        settings = get_settings()
        outline_status = (
            StageStatus.APPROVED.value
            if auto_approve_outline or not settings.require_human_review
            else StageStatus.OUTLINE_REVIEW
        )

        # Save outline to book
        updated_book = save_outline(
            book_id=book["id"],
            outline=outline,
            outline_status=outline_status,
        )

        # Trigger webhook if outline was auto-approved
        if outline_status == StageStatus.APPROVED.value:
            _trigger_outline_approved_webhook(updated_book)

        return updated_book
    except Exception as exc:
        logger.error(f"Failed to create book and outline: {exc}")
        raise


def get_book_response(book_id: UUID) -> BookResponse:
    """Get book and return as response model."""
    book = get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return BookResponse.model_validate(book)


def list_books_response() -> List[BookResponse]:
    """List all books and return as response models."""
    books = list_books()
    return [BookResponse.model_validate(book) for book in books]


def update_outline(
    book_id: UUID,
    human_notes: str,
    status: StageStatus,
) -> BookResponse:
    """Update book outline with human notes and status."""
    try:
        # Update book outline
        updated_book = save_outline(
            book_id=book_id,
            outline=human_notes,  # This seems wrong - should be the outline data, not notes
            status=status.value,
        )

        # If outline is approved, move to chapters phase and trigger webhook
        if status in [StageStatus.APPROVED, StageStatus.NO_NOTES_NEEDED]:
            # Update book phase to chapters
            update_book(
                book_id=book_id,
                phase=BookPhase.CHAPTERS.value
            )
            _trigger_outline_approved_webhook(updated_book)

        return BookResponse.model_validate(updated_book)
    except Exception as exc:
        logger.error(f"Failed to update outline: {exc}")
        raise


def update_final_review(
    book_id: UUID,
    human_notes: Optional[str] = None,
    status: StageStatus = StageStatus.NO_NOTES_NEEDED,
) -> BookResponse:
    """Update book final review status."""
    try:
        updated_book = update_book(
            book_id=book_id,
            final_review_notes_status=status.value,
            human_notes=human_notes,
        )

        # If final review is cleared, mark book as completed
        if status == StageStatus.NO_NOTES_NEEDED:
            update_book(
                book_id=book_id,
                phase=BookPhase.COMPLETED.value
            )

        return BookResponse.model_validate(updated_book)
    except Exception as exc:
        logger.error(f"Failed to update final review: {exc}")
        raise


def generate_next_chapter(book_id: UUID) -> ChapterResponse:
    """Generate the next chapter for a book."""
    try:
        # Ensure outline is approved
        book = get_book(book_id)
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        outline_status = book.get("outline_status")
        if outline_status not in [StageStatus.APPROVED.value, StageStatus.NO_NOTES_NEEDED.value]:
            raise HTTPException(
                status_code=409,
                detail="Outline must be approved before generating chapters"
            )

        # Get next chapter number from outline
        next_chapter_info = get_next_outline_chapter(book_id)
        if not next_chapter_info:
            raise HTTPException(
                status_code=400,
                detail="No more chapters to generate"
            )

        chapter_number = next_chapter_info["chapter_number"]

        # Create chapter stub
        chapter = create_chapter_stub(
            book_id=book_id,
            chapter_number=chapter_number,
            title=next_chapter_info["title"],
        )

        # Get prior chapter summaries for context
        prior_summaries = get_previous_chapter_summaries_before(
            book_id,
            chapter_number
        )

        # Generate chapter content via AI service
        outline_data = OutlineData.model_validate(book["outline"])
        chapter_outline = next(
            (c for c in outline_data.chapters if c.chapter_number == chapter_number),
            None
        )

        if not chapter_outline:
            raise HTTPException(
                status_code=400,
                detail="Chapter outline not found"
            )

        content = ai_service.generate_chapter(
            book_title=book["title"],
            chapter_outline=chapter_outline,
            prior_summaries=prior_summaries,
            human_notes=book.get("human_notes"),
        )

        # Generate summary
        summary = ai_service.summarize_chapter(content)

        # Determine chapter status based on settings
        settings = get_settings()
        chapter_status = (
            StageStatus.PENDING_REVIEW.value
            if settings.require_human_review
            else StageStatus.NO_NOTES_NEEDED.value
        )

        # Update chapter with content and summary
        updated_chapter = update_chapter(
            chapter_id=chapter["id"],
            content=content,
            summary=summary,
            status=chapter_status,
        )

        # Trigger webhook if chapter is auto-approved
        if chapter_status == StageStatus.NO_NOTES_NEEDED.value:
            _trigger_chapter_completed_webhook(updated_chapter)

        return ChapterResponse.model_validate(updated_chapter)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to generate next chapter: {exc}")
        raise


# Constants for chapter generation gating
GENERATABLE_STATUSES = {
    StageStatus.APPROVED.value,
    StageStatus.NO_NOTES_NEEDED.value,
}

BLOCKING_STATUSES = {
    StageStatus.PENDING_REVIEW.value,
    StageStatus.PENDING_NOTES.value,
    "pending",  # alias requested in spec
}


def generate_outline(payload) -> BookResponse:
    """Generate an outline from title/notes and persist to Supabase."""
    try:
        # Import schemas locally to avoid circular imports
        from app.modules.books.schemas import BookResponse, GenerateOutlineRequest, OutlineData

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


def generate_chapter(payload) -> ChapterResponse:
    """
    Generate chapter prose and summary when human gating allows it.
    Requires chapter status of approved or no_notes_needed.
    """
    # Import schemas locally to avoid circular imports
    from app.modules.books.schemas import GenerateChapterRequest, ChapterResponse, OutlineData

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


def get_chapter_response(chapter_id: UUID) -> ChapterResponse:
    """Get chapter and return as response model."""
    chapter = get_chapter(chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return ChapterResponse.model_validate(chapter)


def list_chapters_response(book_id: UUID) -> List[ChapterResponse]:
    """List chapters for a book and return as response models."""
    # Verify book exists
    book = get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    chapters = get_chapters_for_book(book_id)
    return [ChapterResponse.model_validate(chapter) for chapter in chapters]


def update_chapter_with_gate(
    chapter_id: UUID,
    human_notes: Optional[str] = None,
    status: StageStatus = StageStatus.APPROVED,
) -> ChapterResponse:
    """Update chapter with human notes and status, respecting gates."""
    try:
        # Get chapter to verify it exists
        chapter = get_chapter(chapter_id)
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")

        # Update chapter
        updated_chapter = update_chapter(
            chapter_id=chapter_id,
            human_notes=human_notes,
            status=status.value,
        )

        # If chapter is approved, trigger webhook
        if status in [StageStatus.APPROVED, StageStatus.NO_NOTES_NEEDED]:
            _trigger_chapter_completed_webhook(updated_chapter)

        return ChapterResponse.model_validate(updated_chapter)
    except Exception as exc:
        logger.error(f"Failed to update chapter: {exc}")
        raise


def regenerate_chapter_content(chapter_id: UUID) -> ChapterResponse:
    """Regenerate chapter content using existing outline and notes."""
    try:
        # Get chapter
        chapter = get_chapter(chapter_id)
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")

        # Get book
        book = get_book(UUID(chapter["book_id"]))
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        # Get outline
        outline_data = OutlineData.model_validate(book["outline"])
        chapter_outline = next(
            (c for c in outline_data.chapters if c.chapter_number == chapter["chapter_number"]),
            None
        )

        if not chapter_outline:
            raise HTTPException(
                status_code=400,
                detail="Chapter outline not found in book"
            )

        # Get prior chapter summaries for context
        prior_summaries = get_previous_chapter_summaries_before(
            UUID(chapter["book_id"]),
            chapter["chapter_number"],
        )

        # Generate new content
        content = ai_service.generate_chapter(
            book_title=book["title"],
            chapter_outline=chapter_outline,
            prior_summaries=prior_summaries,
            human_notes=chapter.get("human_notes"),
        )

        # Generate new summary
        summary = ai_service.summarize_chapter(content)

        # Reset status to pending review
        settings = get_settings()
        new_status = (
            StageStatus.PENDING_REVIEW.value
            if settings.require_human_review
            else StageStatus.NO_NOTES_NEEDED.value
        )

        # Update chapter
        updated_chapter = update_chapter(
            chapter_id=chapter_id,
            content=content,
            summary=summary,
            status=new_status,
        )

        return ChapterResponse.model_validate(updated_chapter)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to regenerate chapter content: {exc}")
        raise


def moderate_chapter_content(chapter_id: UUID) -> ChapterResponse:
    """Moderate chapter content and update status accordingly."""
    try:
        # Get chapter
        chapter = get_chapter(chapter_id)
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")

        # Get book
        book = get_book(UID(chapter["book_id"]))
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        # Moderate content via moderation service
        is_approved = moderation_service.validate_content(chapter["content"] or "")

        # Update chapter based on moderation result
        if is_approved:
            # Content approved - set to approved status
            updated_chapter = update_chapter(
                chapter_id=chapter_id,
                status=StageStatus.APPROVED.value,
                human_notes=(chapter.get("human_notes") or "") +
                           "\n[Moderation: Content approved]",
            )
        else:
            # Content rejected - set to pending notes
            updated_chapter = update_chapter(
                chapter_id=chapter_id,
                status=StageStatus.PENDING_NOTES.value,
                human_notes=(chapter.get("human_notes") or "") +
                           "\n[Moderation: Content rejected - violates content policy]",
            )

        return ChapterResponse.model_validate(updated_chapter)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to moderate chapter content: {exc}")
        raise


def compile_book_content(book_id: UUID) -> str:
    """Compile book content for export."""
    try:
        # Get book
        book = get_book(book_id)
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        # Check if book is ready for compilation
        if book.get("phase") != BookPhase.COMPLETED.value:
            raise HTTPException(
                status_code=409,
                detail="Book must be completed before compilation"
            )

        # Check final review status
        final_review_status = book.get("final_review_notes_status")
        if final_review_status != StageStatus.NO_NOTES_NEEDED.value:
            raise HTTPException(
                status_code=409,
                detail="Final review must be cleared before compilation"
            )

        # Get compiled text from database service
        compiled_text = db_service.compile_book_text(book_id)
        if not compiled_text:
            raise HTTPException(
                status_code=404,
                detail="No content found to compile"
            )

        return compiled_text
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to compile book content: {exc}")
        raise


def get_book_draft(book_id: UUID) -> BookDraftResponse:
    """Get complete book draft with all chapters."""
    try:
        # Get book
        book = get_book(book_id)
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        # Get chapters
        chapters = get_chapters_for_book(book_id)
        chapter_responses = [ChapterResponse.model_validate(ch) for ch in chapters]

        # Get full text
        full_text = compile_book_content(book_id)

        return BookDraftResponse(
            book=BookResponse.model_validate(book),
            chapters=chapter_responses,
            full_text=full_text,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get book draft: {exc}")
        raise


def _trigger_outline_approved_webhook(book: Dict[str, Any]) -> None:
    """Trigger outline approved webhook (async, fire-and-forget)."""
    try:
        # This would normally be async, but for now we'll just log
        # In a full implementation, this would use background tasks
        logger.info(f"Outline approved webhook triggered for book {book['id']}")
        # TODO: Implement actual webhook calling
    except Exception as exc:
        logger.error(f"Failed to trigger outline approved webhook: {exc}")


def _trigger_chapter_completed_webhook(chapter: Dict[str, Any]) -> None:
    """Trigger chapter completed webhook (async, fire-and-forget)."""
    try:
        # This would normally be async, but for now we'll just log
        # In a full implementation, this would use background tasks
        logger.info(f"Chapter completed webhook triggered for chapter {chapter['id']}")
        # TODO: Implement actual webhook calling
    except Exception as exc:
        logger.error(f"Failed to trigger chapter completed webhook: {exc}")


# Settings import (local to avoid circular imports)
from app.core.config import get_settings