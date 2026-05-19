from collections.abc import Callable
from typing import Any, TypeVar
from uuid import UUID

from supabase import Client, create_client

from app.core.config import get_settings
from app.models import BookPhase, OutlineChapterItem, OutlineData, StageStatus
from app.services.supabase_errors import raise_http_from_supabase

_client: Client | None = None
T = TypeVar("T")


def _reset_client() -> None:
    global _client
    _client = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        settings = get_settings()
        _client = create_client(settings.supabase_url, settings.supabase_key)
    return _client


def _run(operation: Callable[[], T]) -> T:
    """Execute a Supabase operation with consistent error handling."""
    try:
        return operation()
    except Exception as exc:
        from app.services.supabase_errors import _is_connection_error

        if _is_connection_error(exc):
            _reset_client()
        raise_http_from_supabase(exc)


def check_supabase_health() -> tuple[str, str | None]:
    """Verify DB connectivity and schema. Returns (status, error_detail)."""
    try:
        _run(lambda: get_supabase().table("books").select("id").limit(1).execute())
        return "ok", None
    except Exception as exc:
        return "error", str(exc)


# --- Books ---

def create_book(title: str, initial_notes: str | None = None) -> dict[str, Any]:
    payload = {
        "title": title,
        "initial_notes": initial_notes,
        "outline_status": StageStatus.PENDING_REVIEW.value,
        "final_review_notes_status": StageStatus.PENDING_REVIEW.value,
        "phase": BookPhase.OUTLINE.value,
    }

    def _insert() -> dict[str, Any]:
        result = get_supabase().table("books").insert(payload).execute()
        return result.data[0]

    return _run(_insert)


def list_books() -> list[dict[str, Any]]:
    def _fetch() -> list[dict[str, Any]]:
        result = (
            get_supabase()
            .table("books")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []

    return _run(_fetch)


def get_book(book_id: UUID) -> dict[str, Any] | None:
    def _fetch() -> dict[str, Any] | None:
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
    notes: str | None,
    outline: OutlineData,
    outline_status: StageStatus = StageStatus.OUTLINE_REVIEW,
) -> dict[str, Any]:
    payload = {
        "title": title,
        "initial_notes": notes,
        "outline": outline.model_dump(),
        "outline_status": outline_status.value,
        "final_review_notes_status": StageStatus.PENDING_REVIEW.value,
        "phase": BookPhase.OUTLINE.value,
    }

    def _insert() -> dict[str, Any]:
        result = get_supabase().table("books").insert(payload).execute()
        return result.data[0]

    return _run(_insert)


def compile_book_text(book: dict[str, Any], chapters: list[dict[str, Any]]) -> str:
    """Concatenate chapter content ordered by chapter_number."""
    parts = [f"# {book['title']}\n\n"]
    for chapter in chapters:
        parts.append(
            f"## Chapter {chapter['chapter_number']}: {chapter['title']}\n\n"
        )
        parts.append(chapter.get("content") or "")
        parts.append("\n\n")
    return "".join(parts).rstrip() + "\n"


def save_outline(
    book_id: UUID,
    outline: OutlineData,
    outline_status: StageStatus,
) -> dict[str, Any]:
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


def get_chapter(chapter_id: UUID) -> dict[str, Any] | None:
    def _fetch() -> dict[str, Any] | None:
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


def get_chapters_for_book(book_id: UUID) -> list[dict[str, Any]]:
    def _fetch() -> list[dict[str, Any]]:
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


def get_previous_chapter_summaries(book_id: UUID) -> list[dict[str, Any]]:
    """Return summaries of all completed chapters for context chaining."""

    def _fetch() -> list[dict[str, Any]]:
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
) -> list[dict[str, Any]]:
    """Summaries from chapters strictly before the given chapter number."""

    def _fetch() -> list[dict[str, Any]]:
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
    return len(get_chapters_for_book(book_id))


def get_next_outline_chapter(book: dict[str, Any]) -> OutlineChapterItem | None:
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
