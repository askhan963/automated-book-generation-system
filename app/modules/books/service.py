"""
Business logic layer for books module.
Orchestrates repositories, AI service, export services, and webhooks.
"""
from io import BytesIO
from uuid import UUID
from typing import List, Optional, Dict, Any
from fastapi import HTTPException

from app.core.config import get_settings
from app.modules.auth.schemas import Role, UserResponse
from app.modules.books.repository import (
    get_book,
    list_books,
    update_book,
    create_book_with_outline,
    create_chapter_stub,
    get_chapter,
    get_chapters_for_book,
    get_previous_chapter_summaries_before,
    update_chapter,
    get_next_outline_chapter,
)
from app.modules.books.schemas import (
    BookResponse,
    ChapterResponse,
    BookDraftResponse,
    BookNotesUpdate,
    ChapterNotesUpdate,
    FinalReviewUpdate,
    OutlineData,
    StageStatus,
    BookPhase,
)
from app.services import ai_service, db_service
from app.services import moderation_service
import logging

logger = logging.getLogger(__name__)

GENERATABLE_STATUSES = {
    StageStatus.APPROVED.value,
    StageStatus.NO_NOTES_NEEDED.value,
}

BLOCKING_STATUSES = {
    StageStatus.PENDING_REVIEW.value,
    StageStatus.PENDING_NOTES.value,
    "pending",
}


def _is_admin(user: UserResponse) -> bool:
    return user.role == Role.ADMIN


def assert_book_access(book: dict[str, Any], user: UserResponse) -> None:
    """Raise 403 if the user does not own the book (admins bypass)."""
    if _is_admin(user):
        return
    owner = book.get("owner_id")
    if owner is None or str(owner) != str(user.id):
        raise HTTPException(status_code=403, detail="Not the owner of this book")


def get_owned_book(book_id: UUID, user: UserResponse) -> dict[str, Any]:
    book = get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    assert_book_access(book, user)
    return book


def create_book_and_outline(
    title: str,
    initial_notes: Optional[str] = None,
    genre: Optional[str] = None,
    tone: Optional[str] = None,
    audience: Optional[str] = None,
    length: Optional[str] = None,
    auto_approve_outline: bool = False,
    owner_id: Optional[UUID] = None,
) -> BookResponse:
    """Create a book and generate/save its outline."""
    try:
        settings = get_settings()
        outline = ai_service.generate_outline(
            title=title,
            initial_notes=initial_notes,
            genre=genre,
            tone=tone,
            audience=audience,
            length=length,
        )
        outline_status = (
            StageStatus.APPROVED
            if auto_approve_outline or not settings.require_human_review
            else StageStatus.OUTLINE_REVIEW
        )
        book = create_book_with_outline(
            title=title,
            notes=initial_notes,
            outline=outline,
            outline_status=outline_status,
            genre=genre,
            tone=tone,
            audience=audience,
            length=length,
            owner_id=owner_id,
        )
        # Align phase when auto-approved
        if outline_status in (StageStatus.APPROVED, StageStatus.NO_NOTES_NEEDED):
            book = update_book(book_id=UUID(book["id"]), phase=BookPhase.CHAPTERS.value)
            _trigger_outline_approved_webhook(book)

        return BookResponse.model_validate(book)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to create book and outline: {exc}")
        raise HTTPException(status_code=502, detail=f"Book creation failed: {exc}") from exc


def get_book_response(book_id: UUID, user: UserResponse) -> BookResponse:
    book = get_owned_book(book_id, user)
    return BookResponse.model_validate(book)


def list_books_response(user: UserResponse) -> List[BookResponse]:
    owner_filter = None if _is_admin(user) else user.id
    books = list_books(owner_id=owner_filter)
    return [BookResponse.model_validate(book) for book in books]


def update_outline(
    book_id: UUID,
    payload: BookNotesUpdate,
    user: UserResponse,
) -> BookResponse:
    """Human-in-the-loop: add notes and approve/reject outline stage."""
    book = get_owned_book(book_id, user)
    try:
        fields: Dict[str, Any] = {
            "human_notes": payload.human_notes,
            "outline_status": payload.status.value,
        }
        if payload.status in (StageStatus.APPROVED, StageStatus.NO_NOTES_NEEDED):
            fields["phase"] = BookPhase.CHAPTERS.value
        else:
            fields["phase"] = BookPhase.OUTLINE.value

        updated_book = update_book(book_id, **fields)

        if payload.status in (StageStatus.APPROVED, StageStatus.NO_NOTES_NEEDED):
            _trigger_outline_approved_webhook(updated_book)

        return BookResponse.model_validate(updated_book)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to update outline: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def update_final_review(
    book_id: UUID,
    payload: FinalReviewUpdate,
    user: UserResponse,
) -> BookResponse:
    """Human-in-the-loop: clear final review so compile/export is allowed."""
    get_owned_book(book_id, user)
    try:
        fields: Dict[str, Any] = {
            "final_review_notes_status": payload.status.value,
        }
        if payload.human_notes is not None:
            fields["human_notes"] = payload.human_notes
        if payload.status == StageStatus.NO_NOTES_NEEDED:
            fields["phase"] = BookPhase.COMPLETED.value

        updated_book = update_book(book_id, **fields)
        return BookResponse.model_validate(updated_book)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to update final review: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def generate_next_chapter(book_id: UUID, user: UserResponse) -> ChapterResponse:
    """Generate the next chapter for a book."""
    book = get_owned_book(book_id, user)
    try:
        outline_status = book.get("outline_status")
        if outline_status not in (
            StageStatus.APPROVED.value,
            StageStatus.NO_NOTES_NEEDED.value,
        ):
            raise HTTPException(
                status_code=409,
                detail="Outline must be approved before generating chapters",
            )

        next_chapter_info = get_next_outline_chapter(book)
        if not next_chapter_info:
            raise HTTPException(status_code=400, detail="No more chapters to generate")

        chapter_number = next_chapter_info.chapter_number
        chapter = create_chapter_stub(
            book_id=book_id,
            chapter_number=chapter_number,
            title=next_chapter_info.title,
        )

        prior_summaries = get_previous_chapter_summaries_before(book_id, chapter_number)

        content = ai_service.generate_chapter(
            book["title"],
            next_chapter_info,
            prior_summaries,
            book.get("human_notes"),
            genre=book.get("genre"),
            tone=book.get("tone"),
            audience=book.get("audience"),
            length=book.get("length"),
        )
        summary = ai_service.summarize_chapter(content)

        settings = get_settings()
        chapter_status = (
            StageStatus.PENDING_REVIEW.value
            if settings.require_human_review
            else StageStatus.NO_NOTES_NEEDED.value
        )

        updated_chapter = update_chapter(
            chapter_id=UUID(chapter["id"]),
            content=content,
            summary=summary,
            status=chapter_status,
        )

        if chapter_status == StageStatus.NO_NOTES_NEEDED.value:
            _trigger_chapter_completed_webhook(updated_chapter)

        # Move book into chapters phase if still on outline
        if book.get("phase") == BookPhase.OUTLINE.value:
            update_book(book_id, phase=BookPhase.CHAPTERS.value)

        return ChapterResponse.model_validate(updated_chapter)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to generate next chapter: {exc}")
        raise HTTPException(status_code=502, detail=f"Chapter generation failed: {exc}") from exc


def generate_outline(payload, user: UserResponse) -> BookResponse:
    """Generate an outline from title/notes and persist to Supabase."""
    try:
        outline = ai_service.generate_outline(
            title=payload.title,
            initial_notes=payload.notes,
            genre=payload.genre,
            tone=payload.tone,
            audience=payload.audience,
            length=payload.length,
        )
        book = create_book_with_outline(
            title=payload.title,
            notes=payload.notes,
            outline=outline,
            outline_status=StageStatus.OUTLINE_REVIEW,
            genre=payload.genre,
            tone=payload.tone,
            audience=payload.audience,
            length=payload.length,
            owner_id=user.id,
        )
        return BookResponse.model_validate(book)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Outline generation failed: {exc}",
        ) from exc


def generate_chapter(payload, user: UserResponse) -> ChapterResponse:
    """Generate chapter prose when human gating allows it."""
    chapter = get_chapter(payload.chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    book = get_owned_book(UUID(chapter["book_id"]), user)

    status = chapter.get("status", "")
    if status in BLOCKING_STATUSES:
        raise HTTPException(status_code=409, detail="Waiting for human review")
    if status not in GENERATABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Chapter not cleared for generation. Current status: {status}",
        )

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
    prior_summaries = get_previous_chapter_summaries_before(
        book_id,
        chapter["chapter_number"],
    )

    content = ai_service.generate_chapter(
        book["title"],
        chapter_outline,
        prior_summaries,
        chapter.get("human_notes"),
        genre=payload.genre or book.get("genre"),
        tone=payload.tone or book.get("tone"),
        audience=payload.audience or book.get("audience"),
        length=payload.length or book.get("length"),
    )
    summary = ai_service.summarize_chapter(content)

    settings = get_settings()
    new_status = (
        StageStatus.PENDING_REVIEW
        if settings.require_human_review
        else StageStatus.NO_NOTES_NEEDED
    )

    updated = update_chapter(
        payload.chapter_id,
        content=content,
        summary=summary,
        status=new_status.value,
    )
    return ChapterResponse.model_validate(updated)


def get_chapter_response(chapter_id: UUID, user: UserResponse) -> ChapterResponse:
    chapter = get_chapter(chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    get_owned_book(UUID(chapter["book_id"]), user)
    return ChapterResponse.model_validate(chapter)


def list_chapters_response(book_id: UUID, user: UserResponse) -> List[ChapterResponse]:
    get_owned_book(book_id, user)
    chapters = get_chapters_for_book(book_id)
    return [ChapterResponse.model_validate(chapter) for chapter in chapters]


def update_chapter_with_gate(
    chapter_id: UUID,
    payload: ChapterNotesUpdate,
    user: UserResponse,
) -> ChapterResponse:
    """Approve chapter or request revisions with notes."""
    chapter = get_chapter(chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    get_owned_book(UUID(chapter["book_id"]), user)

    try:
        fields: Dict[str, Any] = {"status": payload.status.value}
        if payload.human_notes is not None:
            fields["human_notes"] = payload.human_notes

        updated_chapter = update_chapter(chapter_id=chapter_id, **fields)

        if payload.status in (StageStatus.APPROVED, StageStatus.NO_NOTES_NEEDED):
            _trigger_chapter_completed_webhook(updated_chapter)

        return ChapterResponse.model_validate(updated_chapter)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to update chapter: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def regenerate_chapter_content(chapter_id: UUID, user: UserResponse) -> ChapterResponse:
    """Regenerate chapter content using existing outline and notes."""
    chapter = get_chapter(chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    book = get_owned_book(UUID(chapter["book_id"]), user)
    try:
        outline_data = OutlineData.model_validate(book["outline"])
        chapter_outline = next(
            (
                c
                for c in outline_data.chapters
                if c.chapter_number == chapter["chapter_number"]
            ),
            None,
        )
        if not chapter_outline:
            raise HTTPException(
                status_code=400,
                detail="Chapter outline not found in book",
            )

        prior_summaries = get_previous_chapter_summaries_before(
            UUID(chapter["book_id"]),
            chapter["chapter_number"],
        )

        content = ai_service.generate_chapter(
            book["title"],
            chapter_outline,
            prior_summaries,
            chapter.get("human_notes"),
            genre=book.get("genre"),
            tone=book.get("tone"),
            audience=book.get("audience"),
            length=book.get("length"),
        )
        summary = ai_service.summarize_chapter(content)

        settings = get_settings()
        new_status = (
            StageStatus.PENDING_REVIEW.value
            if settings.require_human_review
            else StageStatus.NO_NOTES_NEEDED.value
        )

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
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def moderate_chapter_content(
    book_id: UUID,
    chapter_id: UUID,
    user: UserResponse,
) -> ChapterResponse:
    """Moderate chapter content and update status accordingly."""
    get_owned_book(book_id, user)
    chapter = get_chapter(chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    if str(chapter["book_id"]) != str(book_id):
        raise HTTPException(status_code=400, detail="Chapter does not belong to book")

    try:
        is_approved = True
        try:
            moderation_service.validate_content(chapter.get("content") or "")
        except HTTPException:
            is_approved = False

        notes = chapter.get("human_notes") or ""
        if is_approved:
            updated_chapter = update_chapter(
                chapter_id=chapter_id,
                status=StageStatus.APPROVED.value,
                human_notes=f"{notes}\n[Moderation: Content approved]".strip(),
            )
        else:
            updated_chapter = update_chapter(
                chapter_id=chapter_id,
                status=StageStatus.PENDING_NOTES.value,
                human_notes=(
                    f"{notes}\n[Moderation: Content rejected - violates content policy]"
                ).strip(),
            )

        return ChapterResponse.model_validate(updated_chapter)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to moderate chapter content: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _build_compiled_text(book: dict[str, Any], chapters: list[dict[str, Any]]) -> str:
    return db_service.compile_book_text(book, chapters)


def compile_book_content(book_id: UUID, user: UserResponse) -> BytesIO:
    """Compile book content for download (requires final review cleared)."""
    book = get_owned_book(book_id, user)

    if book.get("final_review_notes_status") != StageStatus.NO_NOTES_NEEDED.value:
        raise HTTPException(
            status_code=409,
            detail="Final review must be cleared before compilation",
        )

    chapters = get_chapters_for_book(book_id)
    if not chapters:
        raise HTTPException(status_code=404, detail="No content found to compile")

    compiled_text = _build_compiled_text(book, chapters)
    return BytesIO(compiled_text.encode("utf-8"))


def get_book_draft(book_id: UUID, user: UserResponse) -> BookDraftResponse:
    """Get complete book draft with all chapters (no final-review gate)."""
    book = get_owned_book(book_id, user)
    chapters = get_chapters_for_book(book_id)
    chapter_responses = [ChapterResponse.model_validate(ch) for ch in chapters]
    full_text = _build_compiled_text(book, chapters)
    return BookDraftResponse(
        book=BookResponse.model_validate(book),
        chapters=chapter_responses,
        full_text=full_text,
    )


def _trigger_outline_approved_webhook(book: Dict[str, Any]) -> None:
    try:
        logger.info(f"Outline approved webhook triggered for book {book['id']}")
    except Exception as exc:
        logger.error(f"Failed to trigger outline approved webhook: {exc}")


def _trigger_chapter_completed_webhook(chapter: Dict[str, Any]) -> None:
    try:
        logger.info(f"Chapter completed webhook triggered for chapter {chapter['id']}")
    except Exception as exc:
        logger.error(f"Failed to trigger chapter completed webhook: {exc}")
