import re
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.models import (
    BookCreateRequest,
    BookDraftResponse,
    BookNotesUpdate,
    BookPhase,
    BookResponse,
    FinalReviewUpdate,
    ChapterNotesUpdate,
    ChapterResponse,
    HealthResponse,
    MessageResponse,
    OutlineData,
    ServiceHealth,
    StageStatus,
)
from app.services import ai_service, db_service

router = APIRouter(prefix="/api/v1", tags=["books"])


def _book_response(row: dict) -> BookResponse:
    return BookResponse.model_validate(row)


def _chapter_response(row: dict) -> ChapterResponse:
    return ChapterResponse.model_validate(row)


def _ensure_outline_approved(book: dict) -> None:
    if book["outline_status"] not in (
        StageStatus.APPROVED.value,
        StageStatus.NO_NOTES_NEEDED.value,
    ):
        raise HTTPException(
            status_code=409,
            detail=f"Outline not approved. Current status: {book['outline_status']}",
        )


@router.post("/books", response_model=BookResponse)
def create_book_and_outline(payload: BookCreateRequest):
    """
    Phase 1: Create book, generate outline via OpenAI, save to Supabase.
    Pauses at pending_review unless auto_approve_outline is set.
    """
    book = db_service.create_book(payload.title, payload.initial_notes)
    book_id = UUID(book["id"])

    outline = ai_service.generate_outline(payload.title, payload.initial_notes)

    settings = get_settings()
    if payload.auto_approve_outline:
        outline_status = StageStatus.NO_NOTES_NEEDED
    elif settings.require_human_review:
        outline_status = StageStatus.PENDING_REVIEW
    else:
        outline_status = StageStatus.NO_NOTES_NEEDED

    updated = db_service.save_outline(book_id, outline, outline_status)
    return _book_response(updated)


@router.get("/books/{book_id}", response_model=BookResponse)
def get_book(book_id: UUID):
    book = db_service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return _book_response(book)


@router.patch("/books/{book_id}/outline", response_model=BookResponse)
def update_outline_gate(book_id: UUID, payload: BookNotesUpdate):
    """Human-in-the-loop: add notes and approve/reject outline stage."""
    book = db_service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    phase = "chapters" if payload.status in (
        StageStatus.APPROVED,
        StageStatus.NO_NOTES_NEEDED,
    ) else "outline"

    updated = db_service.update_book(
        book_id,
        human_notes=payload.human_notes,
        outline_status=payload.status.value,
        phase=phase,
    )
    return _book_response(updated)


@router.patch("/books/{book_id}/final-review", response_model=BookResponse)
def update_final_review(book_id: UUID, payload: FinalReviewUpdate):
    """Human-in-the-loop: clear final review so GET /compile is allowed."""
    book = db_service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    fields: dict = {"final_review_notes_status": payload.status.value}
    if payload.human_notes is not None:
        fields["human_notes"] = payload.human_notes
    if payload.status == StageStatus.NO_NOTES_NEEDED:
        fields["phase"] = BookPhase.COMPLETED.value

    updated = db_service.update_book(book_id, **fields)
    return _book_response(updated)


@router.post("/books/{book_id}/chapters/next", response_model=ChapterResponse)
def generate_next_chapter(book_id: UUID):
    """
    Phase 2: Generate one chapter at a time using prior chapter summaries as context.
    """
    book = db_service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    _ensure_outline_approved(book)

    next_item = db_service.get_next_outline_chapter(book)
    if not next_item:
        db_service.update_book(book_id, phase="completed")
        raise HTTPException(status_code=400, detail="All chapters already generated")

    settings = get_settings()
    initial_status = (
        StageStatus.PENDING_REVIEW
        if settings.require_human_review
        else StageStatus.NO_NOTES_NEEDED
    )

    chapter_row = db_service.create_chapter_stub(
        book_id,
        next_item.chapter_number,
        next_item.title,
        status=initial_status,
    )
    chapter_id = UUID(chapter_row["id"])

    prior_summaries = db_service.get_previous_chapter_summaries(book_id)
    human_notes = book.get("human_notes")

    content = ai_service.generate_chapter(
        book["title"],
        next_item,
        prior_summaries,
        human_notes,
    )
    summary = ai_service.summarize_chapter(content)

    updated = db_service.update_chapter(
        chapter_id,
        content=content,
        summary=summary,
        status=initial_status.value,
    )
    return _chapter_response(updated)


@router.get("/books/{book_id}/chapters", response_model=list[ChapterResponse])
def list_chapters(book_id: UUID):
    book = db_service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return [_chapter_response(c) for c in db_service.get_chapters_for_book(book_id)]


@router.patch("/chapters/{chapter_id}", response_model=ChapterResponse)
def update_chapter_gate(chapter_id: UUID, payload: ChapterNotesUpdate):
    """Human-in-the-loop: approve chapter or request revisions with notes."""
    chapter = db_service.get_chapter(chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    fields: dict = {"status": payload.status.value}
    if payload.human_notes is not None:
        fields["human_notes"] = payload.human_notes

    updated = db_service.update_chapter(chapter_id, **fields)
    return _chapter_response(updated)


@router.post("/chapters/{chapter_id}/regenerate", response_model=ChapterResponse)
def regenerate_chapter(chapter_id: UUID):
    """Regenerate a chapter using human_notes and prior summaries."""
    chapter = db_service.get_chapter(chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    book = db_service.get_book(UUID(chapter["book_id"]))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    outline = OutlineData.model_validate(book["outline"])
    item = next(
        (c for c in outline.chapters if c.chapter_number == chapter["chapter_number"]),
        None,
    )
    if not item:
        raise HTTPException(status_code=400, detail="Chapter not in outline")

    prior = db_service.get_previous_chapter_summaries(UUID(book["id"]))
    prior = [p for p in prior if p["chapter_number"] < chapter["chapter_number"]]

    content = ai_service.generate_chapter(
        book["title"],
        item,
        prior,
        chapter.get("human_notes"),
    )
    summary = ai_service.summarize_chapter(content)

    updated = db_service.update_chapter(
        chapter_id,
        content=content,
        summary=summary,
        status=StageStatus.PENDING_REVIEW.value,
    )
    return _chapter_response(updated)


@router.get("/books/{book_id}/compile")
def compile_book(book_id: UUID):
    """
    Download compiled book as plain text.
    Requires final_review_notes_status == no_notes_needed.
    """
    book = db_service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if book.get("final_review_notes_status") != StageStatus.NO_NOTES_NEEDED.value:
        raise HTTPException(
            status_code=403,
            detail=(
                "Book cannot be compiled until final review is cleared. "
                "Set final_review_notes_status to no_notes_needed."
            ),
        )

    chapters = db_service.get_chapters_for_book(book_id)
    if not chapters:
        raise HTTPException(status_code=400, detail="No chapters found for this book")

    full_text = db_service.compile_book_text(book, chapters)
    buffer = BytesIO(full_text.encode("utf-8"))

    safe_title = re.sub(r"[^\w\s-]", "", book["title"]).strip().replace(" ", "_")
    filename = f"{safe_title or 'book'}_{book_id}.txt"

    return StreamingResponse(
        buffer,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/books/{book_id}/draft", response_model=BookDraftResponse)
def compile_draft(book_id: UUID):
    """Compilation: fetch all chapters and return full draft text."""
    book = db_service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    chapters = db_service.get_chapters_for_book(book_id)
    if not chapters:
        raise HTTPException(status_code=400, detail="No chapters generated yet")

    parts = [f"# {book['title']}\n"]
    if book.get("outline"):
        parts.append("\n## Outline\n")
        outline = OutlineData.model_validate(book["outline"])
        for ch in outline.chapters:
            parts.append(f"- Ch {ch.chapter_number}: {ch.title} — {ch.brief}\n")

    for ch in chapters:
        parts.append(f"\n\n## Chapter {ch['chapter_number']}: {ch['title']}\n\n")
        parts.append(ch.get("content") or "[Not yet written]")

    full_text = "".join(parts)

    return BookDraftResponse(
        book=_book_response(book),
        chapters=[_chapter_response(c) for c in chapters],
        full_text=full_text,
    )


@router.get("/health", response_model=HealthResponse)
def health():
    supabase_status, supabase_detail = db_service.check_supabase_health()
    openrouter_status, openrouter_detail = ai_service.check_openrouter_health()

    supabase = ServiceHealth(status=supabase_status, detail=supabase_detail)
    openrouter = ServiceHealth(status=openrouter_status, detail=openrouter_detail)

    if supabase_status == "ok" and openrouter_status == "ok":
        overall = "ok"
        message = "All services healthy"
    elif supabase_status == "error" and openrouter_status == "error":
        overall = "error"
        message = "Supabase and OpenRouter are unavailable"
    else:
        overall = "degraded"
        message = "One or more services are unavailable"

    return HealthResponse(
        status=overall,
        message=message,
        supabase=supabase,
        openrouter=openrouter,
    )
