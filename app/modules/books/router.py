"""
API router for book-related endpoints.
HTTP layer only - validates requests and returns responses.
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from app.modules.books.schemas import (
    BookCreateRequest,
    BookResponse,
    BookDraftResponse,
    BookNotesUpdate,
    ChapterNotesUpdate,
    ChapterResponse,
    FinalReviewUpdate,
    GenerateChapterRequest,
    GenerateOutlineRequest,
    HealthResponse,
    MessageResponse,
    ServiceHealth,
    StageStatus,
)
from app.modules.books.service import (
    create_book_and_outline,
    generate_chapter,
    generate_outline,
    get_book_response,
    list_books_response,
    update_outline,
    update_final_review,
    generate_next_chapter,
    get_chapter_response,
    list_chapters_response,
    update_chapter_with_gate,
    regenerate_chapter_content,
    moderate_chapter_content,
    compile_book_content,
    get_book_draft,
)
from app.modules.books.repository import get_supabase
from app.services import ai_service
from app.core.config import get_settings
from app.services.supabase_errors import raise_http_from_supabase
import logging
import re
from io import BytesIO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["books"])


@router.post("/books", response_model=BookResponse)
def create_book_and_outline_endpoint(payload: BookCreateRequest):
    """
    Phase 1: Create book, generate outline via AI, save to repository.
    Pauses at pending_review unless auto_approve_outline is set.
    """
    return create_book_and_outline(
        title=payload.title,
        initial_notes=payload.initial_notes,
        genre=payload.genre,
        tone=payload.tone,
        audience=payload.audience,
        length=payload.length,
        auto_approve_outline=payload.auto_approve_outline,
    )


@router.post("/generate-outline", response_model=BookResponse)
def generate_outline_endpoint(payload: GenerateOutlineRequest):
    """
    Generate outline from title/notes and persist to Supabase.
    Outline status is set to outline_review (pending human review).
    """
    return generate_outline(payload)


@router.post("/generate-chapter", response_model=ChapterResponse)
def generate_chapter_endpoint(payload: GenerateChapterRequest):
    """
    Generate chapter prose and summary when human gating allows it.
    Requires chapter status of approved or no_notes_needed.
    """
    return generate_chapter(payload)


@router.get("/books", response_model=list[BookResponse])
def list_books_endpoint():
    """Return all books, newest first."""
    return list_books_response()


@router.get("/books/{book_id}", response_model=BookResponse)
def get_book_endpoint(book_id: UUID):
    """Get a specific book by ID."""
    return get_book_response(book_id)


@router.patch("/books/{book_id}/outline", response_model=BookResponse)
def update_outline_endpoint(book_id: UUID, payload: BookNotesUpdate):
    """
    Human-in-the-loop: add notes and approve/reject outline stage.
    """
    return update_outline(book_id, payload)


@router.patch("/books/{book_id}/final-review", response_model=BookResponse)
def update_final_review_endpoint(book_id: UUID, payload: FinalReviewUpdate):
    """
    Human-in-the-loop: clear final review so compile endpoint is allowed.
    """
    return update_final_review(book_id, payload)


@router.post("/books/{book_id}/chapters/next", response_model=ChapterResponse)
def generate_next_chapter_endpoint(book_id: UUID):
    """
    Phase 2: Generate one chapter at a time using prior chapter summaries as context.
    """
    return generate_next_chapter(book_id)


@router.get("/books/{book_id}/chapters", response_model=list[ChapterResponse])
def list_chapters_endpoint(book_id: UUID):
    """List all chapters for a specific book."""
    return list_chapters_response(book_id)


@router.patch("/chapters/{chapter_id}", response_model=ChapterResponse)
def update_chapter_endpoint(chapter_id: UUID, payload: ChapterNotesUpdate):
    """
    Human-in-the-loop: approve chapter or request revisions with notes.
    """
    return update_chapter_with_gate(chapter_id, payload)


@router.post("/chapters/{chapter_id}/regenerate", response_model=ChapterResponse)
def regenerate_chapter_endpoint(chapter_id: UUID):
    """Regenerate a chapter using human_notes and prior summaries."""
    return regenerate_chapter_content(chapter_id)


@router.post("/books/{book_id}/chapters/{chapter_id}/moderate", response_model=ChapterResponse)
def moderate_chapter_endpoint(book_id: UUID, chapter_id: UUID):
    """
    Moderate chapter content for quality and appropriateness.
    Runs content through moderation service and updates chapter status if issues found.
    """
    return moderate_chapter_content(book_id, chapter_id)


@router.get("/books/{book_id}/compile")
def compile_book_endpoint(book_id: UUID):
    """
    Download compiled book as plain text.
    Requires final_review_notes_status == no_notes_needed.
    """
    buffer = compile_book_content(book_id)

    book = get_book_response(book_id)
    safe_title = re.sub(r"[^\w\s-]", "", book.title).strip().replace(" ", "_")
    filename = f"{safe_title or 'book'}_{book_id}.txt"

    return StreamingResponse(
        buffer,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/books/{book_id}/draft", response_model=BookDraftResponse)
def get_draft_endpoint(book_id: UUID):
    """Get full draft of a book with all chapters."""
    return get_book_draft(book_id)


# Export endpoints (delegating to export service)
@router.get("/books/{book_id}/export/pdf")
def export_pdf_endpoint(book_id: UUID):
    """Export a book as PDF and return a pre-generated URL."""
    from app.services.export_service import compile_book_pdf, save_export_file
    pdf_bytes = compile_book_pdf(book_id)
    url = save_export_file(book_id, "pdf", pdf_bytes)
    return {"url": url}


@router.get("/books/{book_id}/export/epub")
def export_epub_endpoint(book_id: UUID):
    """Export a book as EPUB and return a pre-generated URL."""
    from app.services.export_service import compile_book_epub, save_export_file
    epub_bytes = compile_book_epub(book_id)
    url = save_export_file(book_id, "epub", epub_bytes)
    return {"url": url}


@router.get("/books/{book_id}/export/markdown")
def export_markdown_endpoint(book_id: UUID):
    """Export a book as Markdown and return a pre-generated URL."""
    from app.services.export_service import compile_book_markdown, save_export_file
    markdown = compile_book_markdown(book_id)
    url = save_export_file(book_id, "md", markdown)
    return {"url": url}


@router.get("/books/{book_id}/export/html")
def export_html_endpoint(book_id: UUID):
    """Export a book as HTML and return a pre-generated URL."""
    from app.services.export_service import compile_book_html, save_export_file
    html = compile_book_html(book_id)
    url = save_export_file(book_id, "html", html)
    return {"url": url}


# Health endpoint (could be moved to a separate health module)
@router.get("/health", response_model=HealthResponse)
def health_endpoint():
    """Health check endpoint for books module."""
    supabase_status, supabase_detail = check_supabase_health()
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
def get_stats_endpoint():
    """Get analytics dashboard statistics."""
    try:
        supabase = get_supabase()
        from datetime import datetime, timedelta
        import logging
        logger = logging.getLogger(__name__)

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


def check_supabase_health() -> tuple[str, str | None]:
    """Verify DB connectivity and schema. Returns (status, error_detail)."""
    try:
        get_supabase().table("books").select("id").limit(1).execute()
        return "ok", None
    except Exception as exc:
        return "error", str(exc)