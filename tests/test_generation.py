"""
Generation logic now lives in the books module (app.modules.books.service).
These tests target the payload-based generate_outline / generate_chapter helpers there.
"""
import pytest
from unittest.mock import patch
from uuid import uuid4
from datetime import datetime

from app.modules.books import service as book_service
from app.modules.books.schemas import (
    GenerateOutlineRequest,
    GenerateChapterRequest,
    BookResponse,
    ChapterResponse,
    StageStatus,
    BookPhase,
    OutlineData,
    OutlineChapterItem,
)
from app.modules.auth.schemas import Role, UserResponse


def make_admin_user():
    return UserResponse(
        id=uuid4(),
        email="admin@example.com",
        role=Role.ADMIN,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def test_generate_outline_success():
    user = make_admin_user()
    payload = GenerateOutlineRequest(
        title="Test Title",
        notes="Some notes",
        genre="Fantasy",
        tone="Epic",
        audience="Young Adult",
        length="Novel",
    )
    outline = OutlineData(
        chapters=[
            OutlineChapterItem(chapter_number=1, title="Chapter 1", brief="Intro"),
            OutlineChapterItem(chapter_number=2, title="Chapter 2", brief="Conflict"),
        ]
    )
    mock_book_dict = {
        "id": str(uuid4()),
        "title": "Test Title",
        "initial_notes": "Some notes",
        "outline": outline.model_dump(),
        "outline_status": StageStatus.OUTLINE_REVIEW.value,
        "final_review_notes_status": StageStatus.PENDING_REVIEW.value,
        "phase": BookPhase.OUTLINE.value,
        "human_notes": None,
        "owner_id": str(user.id),
        "genre": "Fantasy",
        "tone": "Epic",
        "audience": "Young Adult",
        "length": "Novel",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    with patch("app.modules.books.service.create_book_with_outline") as mock_create, \
         patch("app.modules.books.service.ai_service") as mock_ai:
        mock_ai.generate_outline.return_value = outline
        mock_create.return_value = mock_book_dict

        result = book_service.generate_outline(payload, user)

        assert isinstance(result, BookResponse)
        assert result.title == "Test Title"
        assert len(result.outline.chapters) == 2
        mock_ai.generate_outline.assert_called_once_with(
            title="Test Title",
            initial_notes="Some notes",
            genre="Fantasy",
            tone="Epic",
            audience="Young Adult",
            length="Novel",
        )
        mock_create.assert_called_once()


def test_generate_chapter_success():
    user = make_admin_user()
    chapter_id = uuid4()
    book_id = uuid4()
    payload = GenerateChapterRequest(chapter_id=chapter_id)

    mock_chapter = {
        "id": str(chapter_id),
        "book_id": str(book_id),
        "chapter_number": 3,
        "title": "Chapter 3",
        "content": None,
        "summary": None,
        "status": StageStatus.NO_NOTES_NEEDED.value,
        "human_notes": None,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    outline = OutlineData(
        chapters=[OutlineChapterItem(chapter_number=3, title="Chapter 3", brief="Details")]
    )
    mock_book = {
        "id": str(book_id),
        "title": "Test Book",
        "owner_id": str(user.id),
        "outline": outline.model_dump(),
    }

    with patch("app.modules.books.service.get_chapter") as mock_get_chapter, \
         patch("app.modules.books.service.get_book") as mock_get_book, \
         patch("app.modules.books.service.get_previous_chapter_summaries_before") as mock_prev, \
         patch("app.modules.books.service.ai_service") as mock_ai, \
         patch("app.modules.books.service.update_chapter") as mock_update:
        mock_get_chapter.return_value = mock_chapter
        mock_get_book.return_value = mock_book
        mock_prev.return_value = []
        mock_ai.generate_chapter.return_value = "Generated chapter text."
        mock_ai.summarize_chapter.return_value = "Summary of chapter."
        mock_update.return_value = {
            **mock_chapter,
            "content": "Generated chapter text.",
            "summary": "Summary of chapter.",
            "status": StageStatus.PENDING_REVIEW.value,
        }

        result = book_service.generate_chapter(payload, user)

        assert isinstance(result, ChapterResponse)
        assert result.content == "Generated chapter text."
        assert result.summary == "Summary of chapter."
        mock_get_chapter.assert_called_once_with(chapter_id)
        mock_ai.generate_chapter.assert_called_once()
        mock_ai.summarize_chapter.assert_called_once()
        mock_update.assert_called_once()
