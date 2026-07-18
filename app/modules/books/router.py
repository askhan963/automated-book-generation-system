"""
API router for book-related endpoints.
HTTP layer only - validates requests and returns responses.
"""
from uuid import UUID
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import StreamingResponse

from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserResponse
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
    ServiceHealth,
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
    list_chapters_response,
    update_chapter_with_gate,
    regenerate_chapter_content,
    moderate_chapter_content,
    compile_book_content,
    get_book_draft,
    get_owned_book,
)
from app.modules.books.repository import get_supabase
from app.services import ai_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1",
    tags=["books"],
)


@router.post("/books", response_model=BookResponse)
def create_book_and_outline_endpoint(
    payload: BookCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """Phase 1: Create book, generate outline via AI, save to repository."""
    return create_book_and_outline(
        title=payload.title,
        initial_notes=payload.initial_notes,
        genre=payload.genre,
        tone=payload.tone,
        audience=payload.audience,
        length=payload.length,
        auto_approve_outline=payload.auto_approve_outline,
        owner_id=current_user.id,
    )


@router.post("/generate-outline", response_model=BookResponse)
def generate_outline_endpoint(
    payload: GenerateOutlineRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """Generate outline from title/notes and persist to Supabase."""
    return generate_outline(payload, current_user)


@router.post("/generate-chapter", response_model=ChapterResponse)
def generate_chapter_endpoint(
    payload: GenerateChapterRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """Generate chapter prose and summary when human gating allows it."""
    return generate_chapter(payload, current_user)


@router.get("/books", response_model=list[BookResponse])
def list_books_endpoint(current_user: UserResponse = Depends(get_current_user)):
    """Return books owned by the current user (all books for admins)."""
    return list_books_response(current_user)


@router.get("/books/{book_id}", response_model=BookResponse)
def get_book_endpoint(
    book_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
):
    """Get a specific book by ID."""
    return get_book_response(book_id, current_user)


@router.patch("/books/{book_id}/outline", response_model=BookResponse)
def update_outline_endpoint(
    book_id: UUID,
    payload: BookNotesUpdate,
    current_user: UserResponse = Depends(get_current_user),
):
    """Human-in-the-loop: add notes and approve/reject outline stage."""
    return update_outline(book_id, payload, current_user)


@router.patch("/books/{book_id}/final-review", response_model=BookResponse)
def update_final_review_endpoint(
    book_id: UUID,
    payload: FinalReviewUpdate,
    current_user: UserResponse = Depends(get_current_user),
):
    """Human-in-the-loop: clear final review so compile endpoint is allowed."""
    return update_final_review(book_id, payload, current_user)


@router.post("/books/{book_id}/chapters/next", response_model=ChapterResponse)
def generate_next_chapter_endpoint(
    book_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
):
    """Phase 2: Generate one chapter at a time using prior chapter summaries."""
    return generate_next_chapter(book_id, current_user)


@router.get("/books/{book_id}/chapters", response_model=list[ChapterResponse])
def list_chapters_endpoint(
    book_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
):
    """List all chapters for a specific book."""
    return list_chapters_response(book_id, current_user)


@router.patch("/chapters/{chapter_id}", response_model=ChapterResponse)
def update_chapter_endpoint(
    chapter_id: UUID,
    payload: ChapterNotesUpdate,
    current_user: UserResponse = Depends(get_current_user),
):
    """Human-in-the-loop: approve chapter or request revisions with notes."""
    return update_chapter_with_gate(chapter_id, payload, current_user)


@router.post("/chapters/{chapter_id}/regenerate", response_model=ChapterResponse)
def regenerate_chapter_endpoint(
    chapter_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
):
    """Regenerate a chapter using human_notes and prior summaries."""
    return regenerate_chapter_content(chapter_id, current_user)


@router.post(
    "/books/{book_id}/chapters/{chapter_id}/moderate",
    response_model=ChapterResponse,
)
def moderate_chapter_endpoint(
    book_id: UUID,
    chapter_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
):
    """Moderate chapter content for quality and appropriateness."""
    return moderate_chapter_content(book_id, chapter_id, current_user)


@router.get("/books/{book_id}/compile")
def compile_book_endpoint(
    book_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
):
    """Download compiled book as plain text."""
    buffer = compile_book_content(book_id, current_user)
    book = get_book_response(book_id, current_user)
    safe_title = re.sub(r"[^\w\s-]", "", book.title).strip().replace(" ", "_")
    filename = f"{safe_title or 'book'}_{book_id}.txt"

    return StreamingResponse(
        buffer,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/books/{book_id}/draft", response_model=BookDraftResponse)
def get_draft_endpoint(
    book_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
):
    """Get full draft of a book with all chapters."""
    return get_book_draft(book_id, current_user)


@router.get("/books/{book_id}/export/pdf")
def export_pdf_endpoint(
    book_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
):
    """Export a book as PDF and return a pre-generated URL."""
    get_owned_book(book_id, current_user)
    from app.services.export_service import compile_book_pdf, save_export_file

    pdf_bytes = compile_book_pdf(book_id)
    url = save_export_file(book_id, "pdf", pdf_bytes)
    return {"url": url}


@router.get("/books/{book_id}/export/epub")
def export_epub_endpoint(
    book_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
):
    """Export a book as EPUB and return a pre-generated URL."""
    get_owned_book(book_id, current_user)
    from app.services.export_service import compile_book_epub, save_export_file

    epub_bytes = compile_book_epub(book_id)
    url = save_export_file(book_id, "epub", epub_bytes)
    return {"url": url}


@router.get("/books/{book_id}/export/markdown")
def export_markdown_endpoint(
    book_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
):
    """Export a book as Markdown and return a pre-generated URL."""
    get_owned_book(book_id, current_user)
    from app.services.export_service import compile_book_markdown, save_export_file

    markdown = compile_book_markdown(book_id)
    url = save_export_file(book_id, "md", markdown)
    return {"url": url}


@router.get("/books/{book_id}/export/html")
def export_html_endpoint(
    book_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
):
    """Export a book as HTML and return a pre-generated URL."""
    get_owned_book(book_id, current_user)
    from app.services.export_service import compile_book_html, save_export_file

    html = compile_book_html(book_id)
    url = save_export_file(book_id, "html", html)
    return {"url": url}


@router.get("/health", response_model=HealthResponse)
def health_endpoint():
    """Health check endpoint (public)."""
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
def get_stats_endpoint(current_user: UserResponse = Depends(get_current_user)):
    """Get analytics dashboard statistics for the current user (all for admins)."""
    try:
        from datetime import datetime, timedelta

        from app.modules.books.service import _is_admin

        supabase = get_supabase()
        owner_id = None if _is_admin(current_user) else str(current_user.id)

        books_query = supabase.table("books").select("id", count="exact")
        if owner_id:
            books_query = books_query.eq("owner_id", owner_id)
        books_result = books_query.execute()
        total_books = books_result.count

        details_query = supabase.table("books").select(
            "id, title, genre, tone, audience, length, created_at"
        )
        if owner_id:
            details_query = details_query.eq("owner_id", owner_id)
        books_with_details = details_query.execute()

        book_ids = [b["id"] for b in (books_with_details.data or [])]
        total_chapters = 0
        book_stats = []
        genre_dist: dict[str, int] = {}
        tone_dist: dict[str, int] = {}
        audience_dist: dict[str, int] = {}
        length_dist: dict[str, int] = {}
        daily_token_usage: dict[str, int] = {}

        for book in books_with_details.data or []:
            book_id = book["id"]
            chapters_count_result = (
                supabase.table("chapters")
                .select("id", count="exact")
                .eq("book_id", book_id)
                .execute()
            )
            chapters_count = chapters_count_result.count or 0
            total_chapters += chapters_count
            estimated_tokens = chapters_count * 500

            book_stats.append(
                {
                    "book_id": book_id,
                    "title": book["title"],
                    "chapters_count": chapters_count,
                    "estimated_token_usage": estimated_tokens,
                }
            )

            for field, dist in (
                ("genre", genre_dist),
                ("tone", tone_dist),
                ("audience", audience_dist),
                ("length", length_dist),
            ):
                value = book.get(field)
                if value:
                    dist[value] = dist.get(value, 0) + 1

            created_at = book.get("created_at")
            if created_at:
                try:
                    if isinstance(created_at, str):
                        date_part = created_at.split("T")[0]
                    else:
                        date_part = created_at.strftime("%Y-%m-%d")
                    daily_token_usage[date_part] = (
                        daily_token_usage.get(date_part, 0) + estimated_tokens
                    )
                except Exception:
                    pass

        today = datetime.now().date()
        token_trends = []
        for i in range(7):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            token_trends.append(
                {
                    "date": date_str,
                    "estimated_tokens": daily_token_usage.get(date_str, 0),
                }
            )
        token_trends.reverse()

        return {
            "total_books": total_books,
            "total_chapters": total_chapters,
            "books": book_stats,
            "writing_style_analytics": {
                "genre_distribution": genre_dist,
                "tone_distribution": tone_dist,
                "audience_distribution": audience_dist,
                "length_distribution": length_dist,
            },
            "token_consumption_trends": token_trends,
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
