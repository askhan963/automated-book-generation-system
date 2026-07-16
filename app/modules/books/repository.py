from collections.abc import Callable
from typing import Any, TypeVar, Optional, List
from uuid import UUID

from supabase import Client

from app.core.dependencies import get_supabase_client
from app.modules.books.schemas import (
    BookPhase,
    OutlineChapterItem,
    OutlineData,
    StageStatus,
)
from app.services.supabase_errors import raise_http_from_supabase

_client: Optional[Client] = None
T = TypeVar("T")


def get_supabase() -> Client:
    """Get Supabase client instance."""
    global _client
    if _client is None:
        _client = get_supabase_client()
    return _client


def _run(operation: Callable[[], T]) -> T:
    """Execute a Supabase operation with consistent error handling."""
    try:
        return operation()
    except Exception as exc:
        from app.services.supabase_errors import _is_connection_error

        if _is_connection_error(exc):
            # Reset client on connection error
            global _client
            _client = None
        raise_http_from_supabase(exc)


# --- Books ---

def create_book(
    title: str,
    initial_notes: Optional[str] = None,
    genre: Optional[str] = None,
    tone: Optional[str] = None,
    audience: Optional[str] = None,
    length: Optional[str] = None,
) -> dict[str, Any]:
    """Create a new book record."""
    payload = {
        "title": title,
        "initial_notes": initial_notes,
        "outline_status": StageStatus.PENDING_REVIEW.value,
        "final_review_notes_status": StageStatus.PENDING_REVIEW.value,
        "phase": BookPhase.OUTLINE.value,
        "genre": genre,
        "tone": tone,
        "audience": audience,
        "length": length,
    }

    def _insert() -> dict[str, Any]:
        result = get_supabase().table("books").insert(payload).execute()
        return result.data[0]

    return _run(_insert)


def list_books() -> List[dict[str, Any]]:
    """List all books ordered by creation date (newest first)."""
    def _fetch() -> List[dict[str, Any]]:
        result = (
            get_supabase()
            .table("books")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []

    return _run(_fetch)


def get_book(book_id: UUID) -> Optional[dict[str, Any]]:
    """Get a book by ID."""
    def _fetch() -> Optional[dict[str, Any]]:
        result = (
            get_supabase()
            .table("books")
            .select("*")
            .eq("id", str(book_id))
            .maybe_single()
            .execute()
        )
        return result.data

    return _run(_fetch)


def update_book(book_id: UUID, **fields: Any) -> dict[str, Any]:
    """Update a book record."""
    def _update() -> dict[str, Any]:
        result = (
            get_supabase()
            .table("books")
            .update(fields)
            .eq("id", str(book_id))
            .execute()
        )
        return result.data[0]

    return _run(_update)


def create_book_with_outline(
    title: str,
    notes: Optional[str],
    outline: OutlineData,
    outline_status: StageStatus = StageStatus.OUTLINE_REVIEW,
    genre: Optional[str] = None,
    tone: Optional[str] = None,
    audience: Optional[str] = None,
    length: Optional[str] = None,
) -> dict[str, Any]:
    """Create a book with an initial outline."""
    payload = {
        "title": title,
        "initial_notes": notes,
        "outline": outline.model_dump(),
        "outline_status": outline_status.value,
        "final_review_notes_status": StageStatus.PENDING_REVIEW.value,
        "phase": BookPhase.OUTLINE.value,
        "genre": genre,
        "tone": tone,
        "audience": audience,
        "length": length,
    }

    def _insert() -> dict[str, Any]:
        result = get_supabase().table("books").insert(payload).execute()
        return result.data[0]

    return _run(_insert)


def save_outline(
    book_id: UUID,
    outline: OutlineData,
    outline_status: StageStatus,
) -> dict[str, Any]:
    """Save or update a book's outline."""
    return update_book(
        book_id,
        outline=outline.model_dump(),
        outline_status=outline_status.value,
        phase=BookPhase.CHAPTERS.value
        if outline_status in (StageStatus.APPROVED, StageStatus.NO_NOTES_NEEDED)
        else BookPhase.OUTLINE.value,
    )


# --- Chapters ---

def create_chapter_stub(
    book_id: UUID,
    chapter_number: int,
    title: str,
    status: StageStatus = StageStatus.PENDING_REVIEW,
) -> dict[str, Any]:
    """Create a chapter stub (placeholder) record."""
    payload = {
        "book_id": str(book_id),
        "chapter_number": chapter_number,
        "title": title,
        "status": status.value,
    }

    def _insert() -> dict[str, Any]:
        result = get_supabase().table("chapters").insert(payload).execute()
        return result.data[0]

    return _run(_insert)


def get_chapter(chapter_id: UUID) -> Optional[dict[str, Any]]:
    """Get a chapter by ID."""
    def _fetch() -> Optional[dict[str, Any]]:
        result = (
            get_supabase()
            .table("chapters")
            .select("*")
            .eq("id", str(chapter_id))
            .maybe_single()
            .execute()
        )
        return result.data

    return _run(_fetch)


def get_chapters_for_book(book_id: UUID) -> List[dict[str, Any]]:
    """Get all chapters for a book ordered by chapter number."""
    def _fetch() -> List[dict[str, Any]]:
        result = (
            get_supabase()
            .table("chapters")
            .select("*")
            .eq("book_id", str(book_id))
            .order("chapter_number")
            .execute()
        )
        return result.data or []

    return _run(_fetch)


def get_previous_chapter_summaries(book_id: UUID) -> List[dict[str, Any]]:
    """Return summaries of all completed chapters for context chaining."""
    def _fetch() -> List[dict[str, Any]]:
        result = (
            get_supabase()
            .table("chapters")
            .select("chapter_number, title, summary")
            .eq("book_id", str(book_id))
            .not_.is_("summary", "null")
            .order("chapter_number")
            .execute()
        )
        return result.data or []

    return _run(_fetch)


def get_previous_chapter_summaries_before(
    book_id: UUID,
    chapter_number: int,
) -> List[dict[str, Any]]:
    """Summaries from chapters strictly before the given chapter number."""
    def _fetch() -> List[dict[str, Any]]:
        result = (
            get_supabase()
            .table("chapters")
            .select("chapter_number, title, summary")
            .eq("book_id", str(book_id))
            .lt("chapter_number", chapter_number)
            .not_.is_("summary", "null")
            .order("chapter_number")
            .execute()
        )
        return result.data or []

    return _run(_fetch)


def update_chapter(chapter_id: UUID, **fields: Any) -> dict[str, Any]:
    """Update a chapter record."""
    def _update() -> dict[str, Any]:
        result = (
            get_supabase()
            .table("chapters")
            .update(fields)
            .eq("id", str(chapter_id))
            .execute()
        )
        return result.data[0]

    return _run(_update)


def count_chapters(book_id: UUID) -> int:
    """Count chapters for a book."""
    return len(get_chapters_for_book(book_id))


def get_next_outline_chapter(book: dict[str, Any]) -> Optional[OutlineChapterItem]:
    """Return the next chapter from outline that has not been generated yet."""
    outline_raw = book.get("outline")
    if not outline_raw:
        return None

    outline = OutlineData.model_validate(outline_raw)
    existing = {c["chapter_number"] for c in get_chapters_for_book(UUID(book["id"]))}

    for item in outline.chapters:
        if item.chapter_number not in existing:
            return item
    return None