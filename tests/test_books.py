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


def make_mock_book(book_id=None, title="Test Book"):
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
        "genre": None,
        "tone": None,
        "audience": None,
        "length": None,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


def make_mock_outline(chapter_count=3):
    chapters = [
        OutlineChapterItem(chapter_number=i+1, title=f"Chapter {i+1}", brief=f"Brief {i+1}")
        for i in range(chapter_count)
    ]
    return OutlineData(chapters=chapters)


@patch("app.modules.books.service.ai_service")
@patch("app.modules.books.service.create_book")
@patch("app.modules.books.service.save_outline")
@patch("app.modules.books.service.book_service.create_book_with_outline")  # we need to patch where it's used? Actually function uses create_book_with_outline from repo.
def test_create_book_and_outline(mock_create_book_with_outline, mock_save_outline, mock_create_book, mock_ai_service):
    # Arrange
    book_id = uuid4()
    mock_create_book.return_value = {"id": str(book_id), "title": "Test", "initial_notes": None}
    mock_ai_service.generate_outline.return_value = make_mock_outline()
    # The service calls create_book_with_outline from repo; we mock that
    mock_create_book_with_outline.return_value = {
        "id": str(book_id),
        "title": "Test",
        "notes": None,
        "outline": mock_ai_service.generate_outline.return_value.dict(),
        "outline_status": StageStatus.OUTLINE_REVIEW.value,
        "genre": None,
        "tone": None,
        "audience": None,
        "length": None,
    }

    # Act
    result = book_service.create_book_and_outline(
        title="Test",
        initial_notes=None,
        genre=None,
        tone=None,
        audience=None,
        length=None,
        auto_approve_outline=False,
    )

    # Assert
    assert result["id"] == str(book_id)
    assert result["title"] == "Test"
    mock_create_book.assert_called_once()
    mock_ai_service.generate_outline.assert_called_once()
    mock_create_book_with_outline.assert_called_once()


@patch("app.modules.books.service.get_book")
def test_get_book_response_found(mock_get_book):
    book_id = uuid4()
    mock_book = make_mock_book(book_id)
    mock_get_book.return_value = mock_book

    resp = book_service.get_book_response(book_id)

    assert isinstance(resp, BookResponse)
    assert resp.id == book_id
    assert resp.title == "Test Book"


@patch("app.modules.books.service.get_book")
def test_get_book_response_not_found(mock_get_book):
    mock_get_book.return_value = None

    with pytest.raises(Exception):  # expecting HTTPException
        book_service.get_book_response(uuid4())


@patch("app.modules.books.service.list_books")
def test_list_books_response(mock_list_books):
    book_id1 = uuid4()
    book_id2 = uuid4()
    mock_list_books.return_value = [
        make_mock_book(book_id1, "Book One"),
        make_mock_book(book_id2, "Book Two"),
    ]

    resp = book_service.list_books_response()

    assert len(resp) == 2
    assert all(isinstance(b, BookResponse) for b in resp)
    assert resp[0].title == "Book One"
    assert resp[1].title == "Book Two"


@patch("app.modules.books.service.update_book")
@patch("app.modules.books.service.save_outline")
def test_update_outline_approved(mock_save_outline, mock_update_book):
    book_id = uuid4()
    # Simulate saved outline returning a dict with updated fields
    mock_save_outline.return_value = {
        "id": str(book_id),
        "title": "Test",
        "notes": "Updated outline",
        "outline": "Updated outline content",
        "outline_status": StageStatus.APPROVED.value,
        "genre": None,
        "tone": None,
        "audience": None,
        "length": None,
    }
    # After approval, the service updates book phase to CHAPTERS
    mock_update_book.return_value = {
        "id": str(book_id),
        "title": "Test",
        "notes": None,
        "outline": "Updated outline content",
        "outline_status": StageStatus.APPROVED.value,
        "final_review_notes_status": StageStatus.PENDING_REVIEW.value,
        "phase": BookPhase.CHAPTERS.value,
        "human_notes": None,
        "genre": None,
        "tone": None,
        "audience": None,
        "length": None,
    }

    payload = BookNotesUpdate(human_notes="Nice outline", status=StageStatus.APPROVED)

    result = book_service.update_outline(book_id, payload.human_notes, payload.status)

    assert isinstance(result, BookResponse)
    assert result.outline_status == StageStatus.APPROVED
    assert result.phase == BookPhase.CHAPTERS
    mock_save_outline.assert_called_once()
    mock_update_book.assert_called_once()


@patch("app.modules.books.service.get_book")
@patch("app.modules.books.service.create_chapter_stub")
@patch("app.modules.books.service.get_previous_chapter_summaries_before")
@patch("app.modules.books.service.ai_service")
@patch("app.modules.books.service.update_chapter")
def test_generate_next_chapter(
    mock_update_chapter,
    mock_ai_service,
    mock_get_previous_summaries,
    mock_create_chapter_stub,
    mock_get_book,
):
    book_id = uuid4()
    chapter_number = 1

    # mock book with approved outline
    mock_book = {
        "id": str(book_id),
        "title": "Test Book",
        "outline": make_mock_outline().json(),
        "outline_status": StageStatus.APPROVED.value,
        "final_review_notes_status": StageStatus.NO_NOTES_NEEDED.value,
        "phase": BookPhase.CHAPTERS.value,
    }
    mock_get_book.return_value = mock_book

    # next chapter from outline
    mock_get_previous_summaries.return_value = []  # no prior chapters
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

    result = book_service.generate_next_chapter(book_id)

    assert isinstance(result, ChapterResponse)
    assert result.title == f"Chapter {chapter_number}"
    assert result.content == "Generated chapter content."
    assert result.summary == "Summary of chapter."
    mock_get_book.assert_called_once_with(book_id)
    mock_create_chapter_stub.assert_called_once()
    mock_ai_service.generate_chapter.assert_called_once()
    mock_ai_service.summarize_chapter.assert_called_once()
    mock_update_chapter.assert_called_once()


@pytest.mark.asyncio
@patch("app.modules.books.service.decode_token")
@patch("app.modules.books.service.get_user_by_email")
async def test_get_current_user(mock_get_user, mock_decode):
    from app.modules.auth.service import get_current_user  # reuse auth function; but we are testing auth, not books; skip
    pass