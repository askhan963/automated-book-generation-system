import re
from datetime import datetime, timedelta
from io import BytesIO
from uuid import UUID
import logging

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
from app.services import ai_service, db_service, export_service, moderation_service
from app.services.db_service import get_supabase

router = APIRouter(prefix="/api/v1", tags=["books"])
logger = logging.getLogger(__name__)


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
    book = db_service.create_book(
        title=payload.title,
        initial_notes=payload.initial_notes,
        genre=payload.genre,
        tone=payload.tone,
        audience=payload.audience,
        length=payload.length,
    )
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


@router.get("/books", response_model=list[BookResponse])
def list_books():
    """Return all books, newest first."""
    return [_book_response(book) for book in db_service.list_books()]


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

    # Trigger outline approved webhook when outline is approved
    if payload.status in (StageStatus.APPROVED, StageStatus.NO_NOTES_NEEDED):
        try:
            # Get the updated book data for the webhook
            updated_book = db_service.get_book(book_id)
            from app.api.webhooks import outline_approved_webhook, OutlineApprovedWebhook
            import asyncio
            webhook_data = OutlineApprovedWebhook(
                book_id=book_id,
                book_title=updated_book["title"],
                outline_data=updated_book.get("outline", {}),
                approved_by=payload.human_notes or "System",
                approval_notes=payload.human_notes
            )
            # Run the async function (since we're in a sync context)
            try:
                asyncio.run(outline_approved_webhook(webhook_data))
            except RuntimeError:
                # If there's already an event loop, we need to handle it differently
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a task if loop is already running
                    asyncio.create_task(outline_approved_webhook(webhook_data))
                else:
                    loop.run_until_complete(outline_approved_webhook(webhook_data))
            logger.info(f"Outline approved webhook triggered for book {book_id}")
        except Exception as e:
            logger.error(f"Failed to trigger outline approved webhook: {e}")
            # Don't fail the main operation if webhook fails

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

    # Trigger chapter completed webhook when chapter is approved
    if payload.status in (StageStatus.APPROVED, StageStatus.NO_NOTES_NEEDED):
        try:
            # Get the chapter and book data for the webhook
            updated_chapter = db_service.get_chapter(chapter_id)
            book = db_service.get_book(UUID(updated_chapter["book_id"]))
            from app.api.webhooks import chapter_completed_webhook, ChapterCompletedWebhook
            import asyncio
            webhook_data = ChapterCompletedWebhook(
                book_id=UUID(updated_chapter["book_id"]),
                book_title=book["title"],
                chapter_number=updated_chapter["chapter_number"],
                chapter_title=updated_chapter["title"],
                chapter_summary=updated_chapter.get("summary"),
                completed_by=payload.human_notes or "System"
            )
            # Run the async function (since we're in a sync context)
            try:
                asyncio.run(chapter_completed_webhook(webhook_data))
            except RuntimeError:
                # If there's already an event loop, we need to handle it differently
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a task if loop is already running
                    asyncio.create_task(chapter_completed_webhook(webhook_data))
                else:
                    loop.run_until_complete(chapter_completed_webhook(webhook_data))
            logger.info(f"Chapter completed webhook triggered for book {updated_chapter['book_id']} chapter {updated_chapter['chapter_number']}")
        except Exception as e:
            logger.error(f"Failed to trigger chapter completed webhook: {e}")
            # Don't fail the main operation if webhook fails

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


@router.post("/books/{book_id}/chapters/{chapter_id}/moderate", response_model=ChapterResponse)
def moderate_chapter(book_id: UUID, chapter_id: UUID):
    """
    Moderate chapter content for quality and appropriateness.
    Runs content through moderation service and updates chapter status if issues found.
    """
    # Verify book exists
    book = db_service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Verify chapter exists and belongs to this book
    chapter = db_service.get_chapter(chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    if chapter["book_id"] != str(book_id):
        raise HTTPException(status_code=400, detail="Chapter does not belong to this book")

    # Only moderate chapters that have content
    content = chapter.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="Chapter has no content to moderate")

    # Run content through moderation service
    try:
        moderation_service.validate_content(content)
        # If validation passes, chapter is acceptable
        # Update status to indicate it has been moderated and passed
        fields = {
            "status": StageStatus.APPROVED.value,
            "human_notes": f"{chapter.get('human_notes') or ''}\n[Moderation: Content approved]".strip()
        }
    except HTTPException as mod_exception:
        # If validation fails, mark chapter as needing revision
        fields = {
            "status": StageStatus.PENDING_NOTES.value,
            "human_notes": f"{chapter.get('human_notes') or ''}\n[Moderation REJECTED: {mod_exception.detail}]".strip()
        }

    # Remove extra newlines and whitespace from human_notes
    if "human_notes" in fields:
        fields["human_notes"] = " ".join(fields["human_notes"].split())

    updated = db_service.update_chapter(chapter_id, **fields)
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


@router.get("/books/{book_id}/export/pdf")
def export_pdf(book_id: UUID):
    """Export a book as PDF and return a pre‑generated URL."""
    pdf_bytes = export_service.compile_book_pdf(book_id)
    url = export_service.save_export_file(book_id, "pdf", pdf_bytes)
    return {"url": url}

@router.get("/books/{book_id}/export/epub")
def export_epub(book_id: UUID):
    """Export a book as EPUB and return a pre‑generated URL."""
    epub_bytes = export_service.compile_book_epub(book_id)
    url = export_service.save_export_file(book_id, "epub", epub_bytes)
    return {"url": url}

@router.get("/books/{book_id}/export/markdown")
def export_markdown(book_id: UUID):
    """Export a book as Markdown and return a pre‑generated URL."""
    markdown = export_service.compile_book_markdown(book_id)
    url = export_service.save_export_file(book_id, "md", markdown)
    return {"url": url}

@router.get("/books/{book_id}/export/html")
def export_html(book_id: UUID):
    """Export a book as HTML and return a pre‑generated URL."""
    html = export_service.compile_book_html(book_id)
    url = export_service.save_export_file(book_id, "html", html)
    return {"url": url}

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


@router.get("/stats")
def get_analytics():
    """Get analytics dashboard statistics."""
    try:
        supabase = get_supabase()

        # Get total books count
        books_result = supabase.table("books").select("id", count="exact").execute()
        total_books = books_result.count

        # Get total chapters count
        chapters_result = supabase.table("chapters").select("id", count="exact").execute()
        total_chapters = chapters_result.count

        # Get books with their chapter counts and writing style data for analytics
        books_with_details = supabase.table("books").select("id, title, genre, tone, audience, length, created_at").execute()

        # Prepare book stats
        book_stats = []
        # Initialize counters for writing style distributions
        genre_dist = {}
        tone_dist = {}
        audience_dist = {}
        length_dist = {}
        # For token trends over time (group by date)
        daily_token_usage = {}

        for book in books_with_details.data or []:
            book_id = book["id"]
            chapters_count_result = supabase.table("chapters").select("id", count="exact").eq("book_id", book_id).execute()
            chapters_count = chapters_count_result.count

            # Estimated token usage (rough estimate: 500 tokens per chapter)
            estimated_tokens = chapters_count * 500

            book_stats.append({
                "book_id": book_id,
                "title": book["title"],
                "chapters_count": chapters_count,
                "estimated_token_usage": estimated_tokens
            })

            # Count writing style distributions
            genre = book.get("genre")
            if genre:
                genre_dist[genre] = genre_dist.get(genre, 0) + 1

            tone = book.get("tone")
            if tone:
                tone_dist[tone] = tone_dist.get(tone, 0) + 1

            audience = book.get("audience")
            if audience:
                audience_dist[audience] = audience_dist.get(audience, 0) + 1

            length = book.get("length")
            if length:
                length_dist[length] = length_dist.get(length, 0) + 1

            # Track token usage over time (group by date)
            created_at = book.get("created_at")
            if created_at:
                # Extract date part (YYYY-MM-DD)
                try:
                    if isinstance(created_at, str):
                        date_part = created_at.split("T")[0]  # ISO format
                    else:
                        date_part = created_at.strftime("%Y-%m-%d")

                    if date_part not in daily_token_usage:
                        daily_token_usage[date_part] = 0
                    daily_token_usage[date_part] += estimated_tokens
                except Exception:
                    # If date parsing fails, skip this book for time-series data
                    pass

        # Calculate token consumption trends (last 7 days)
        today = datetime.now().date()
        token_trends = []
        for i in range(7):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            token_trends.append({
                "date": date_str,
                "estimated_tokens": daily_token_usage.get(date_str, 0)
            })
        # Reverse to show oldest first
        token_trends.reverse()

        return {
            "total_books": total_books,
            "total_chapters": total_chapters,
            "books": book_stats,
            "writing_style_analytics": {
                "genre_distribution": genre_dist,
                "tone_distribution": tone_dist,
                "audience_distribution": audience_dist,
                "length_distribution": length_dist
            },
            "token_consumption_trends": token_trends
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve analytics: {exc}",
        ) from exc
