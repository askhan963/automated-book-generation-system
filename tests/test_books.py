import pytest
from unittest.mock import patch, MagicMock
from uuid import UUID, uuid4
from datetime import datetime

# Import module to test
from app.modules.books import service as book_service
from app.modules.books.schemas import (
    BookResponse,
    ChapterResponse,
    BookCreateRequest,
    BookNotesUpdate,
    FinalReviewUpdate,
    ChapterNotesUpdate,
    StageStatus,
    BookPhase,
    OutlineData,
    OutlineChapterItem,
)
from app.modules.auth.schemas import Role, UserResponse


def make_admin_user():
    """Admin user bypasses ownership checks in the service layer."""
    return UserResponse(
        id=uuid4(),
        email="admin@example.com",
        role=Role.ADMIN,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def make_mock_book(book_id=None, title="Test Book", owner_id=None):
    if book_id is None:
        book_id = uuid4()
    return {
        "id": str(book_id),
        "title": title,
        "initial_notes": None,
        "outline": None,
        "outline_status": StageStatus.PENDING_REVIEW.value,
        "final_review_notes_status": StageStatus.PENDING_REVIEW.value,
        "phase": BookPhase.OUTLINE.value,
        "human_notes": None,
        "owner_id": str(owner_id) if owner_id else None,
        "genre": None,
        "tone": None,
        "audience": None,
        "length": None,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


def make_mock_outline(chapter_count=3):
    chapters = [
        OutlineChapterItem(chapter_number=i + 1, title=f"Chapter {i+1}", brief=f"Brief {i+1}")
        for i in range(chapter_count)
    ]
    return OutlineData(chapters=chapters)


@patch("app.modules.books.service.ai_service")
@patch("app.modules.books.service.create_book_with_outline")
def test_create_book_and_outline(mock_create_book_with_outline, mock_ai_service):
    user = make_admin_user()
    book_id = uuid4()
    mock_ai_service.generate_outline.return_value = make_mock_outline()
    mock_create_book_with_outline.return_value = make_mock_book(book_id, "Test")

    result = book_service.create_book_and_outline(
        title="Test",
        initial_notes=None,
        genre=None,
        tone=None,
        audience=None,
        length=None,
        auto_approve_outline=False,
        owner_id=user.id,
    )

    assert isinstance(result, BookResponse)
    assert result.id == book_id
    assert result.title == "Test"
    mock_ai_service.generate_outline.assert_called_once()
    mock_create_book_with_outline.assert_called_once()


@patch("app.modules.books.service.get_book")
def test_get_book_response_found(mock_get_book):
    user = make_admin_user()
    book_id = uuid4()
    mock_get_book.return_value = make_mock_book(book_id)

    resp = book_service.get_book_response(book_id, user)

    assert isinstance(resp, BookResponse)
    assert resp.id == book_id
    assert resp.title == "Test Book"


@patch("app.modules.books.service.get_book")
def test_get_book_response_not_found(mock_get_book):
    user = make_admin_user()
    mock_get_book.return_value = None

    with pytest.raises(Exception):  # expecting HTTPException
        book_service.get_book_response(uuid4(), user)


@patch("app.modules.books.service.list_books")
def test_list_books_response(mock_list_books):
    user = make_admin_user()
    book_id1 = uuid4()
    book_id2 = uuid4()
    mock_list_books.return_value = [
        make_mock_book(book_id1, "Book One"),
        make_mock_book(book_id2, "Book Two"),
    ]

    resp = book_service.list_books_response(user)

    assert len(resp) == 2
    assert all(isinstance(b, BookResponse) for b in resp)
    assert resp[0].title == "Book One"
    assert resp[1].title == "Book Two"


@patch("app.modules.books.service.get_book")
@patch("app.modules.books.service.update_book")
def test_update_outline_approved(mock_update_book, mock_get_book):
    user = make_admin_user()
    book_id = uuid4()
    mock_get_book.return_value = make_mock_book(book_id)
    mock_update_book.return_value = {
        **make_mock_book(book_id),
        "outline_status": StageStatus.APPROVED.value,
        "phase": BookPhase.CHAPTERS.value,
        "human_notes": "Nice outline",
    }

    payload = BookNotesUpdate(human_notes="Nice outline", status=StageStatus.APPROVED)
    result = book_service.update_outline(book_id, payload, user)

    assert isinstance(result, BookResponse)
    assert result.outline_status == StageStatus.APPROVED
    assert result.phase == BookPhase.CHAPTERS
    mock_update_book.assert_called_once()


@patch("app.modules.books.service.get_book")
@patch("app.modules.books.service.get_next_outline_chapter")
@patch("app.modules.books.service.create_chapter_stub")
@patch("app.modules.books.service.get_previous_chapter_summaries_before")
@patch("app.modules.books.service.ai_service")
@patch("app.modules.books.service.update_chapter")
def test_generate_next_chapter(
    mock_update_chapter,
    mock_ai_service,
    mock_get_previous_summaries,
    mock_create_chapter_stub,
    mock_get_next_outline_chapter,
    mock_get_book,
):
    user = make_admin_user()
    book_id = uuid4()
    chapter_number = 1

    mock_book = make_mock_book(book_id)
    mock_book["outline"] = make_mock_outline().model_dump()
    mock_book["outline_status"] = StageStatus.APPROVED.value
    mock_book["phase"] = BookPhase.CHAPTERS.value
    mock_get_book.return_value = mock_book

    mock_get_next_outline_chapter.return_value = OutlineChapterItem(
        chapter_number=chapter_number, title=f"Chapter {chapter_number}", brief="Brief 1"
    )
    mock_get_previous_summaries.return_value = []
    mock_create_chapter_stub.return_value = {
        "id": str(uuid4()),
        "book_id": str(book_id),
        "chapter_number": chapter_number,
        "title": f"Chapter {chapter_number}",
        "content": None,
        "summary": None,
        "status": StageStatus.PENDING_REVIEW.value,
    }
    mock_ai_service.generate_chapter.return_value = "Generated chapter content."
    mock_ai_service.summarize_chapter.return_value = "Summary of chapter."
    mock_update_chapter.return_value = {
        "id": str(uuid4()),
        "book_id": str(book_id),
        "chapter_number": chapter_number,
        "title": f"Chapter {chapter_number}",
        "content": "Generated chapter content.",
        "summary": "Summary of chapter.",
        "status": StageStatus.PENDING_REVIEW.value,
        "human_notes": None,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    result = book_service.generate_next_chapter(book_id, user)

    assert isinstance(result, ChapterResponse)
    assert result.title == f"Chapter {chapter_number}"
    assert result.content == "Generated chapter content."
    assert result.summary == "Summary of chapter."
    mock_create_chapter_stub.assert_called_once()
    mock_ai_service.generate_chapter.assert_called_once()
    mock_ai_service.summarize_chapter.assert_called_once()
    mock_update_chapter.assert_called_once()
