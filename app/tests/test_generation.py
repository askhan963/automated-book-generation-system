import pytest
from unittest.mock import patch, MagicMock
from uuid import UUID, uuid4

from app.modules.generation import service as gen_service
from app.modules.books.schemas import GenerateOutlineRequest, GenerateChapterRequest, BookResponse, ChapterResponse, StageStatus


def test_generate_outline_success():
    # Arrange
    payload = GenerateOutlineRequest(
        title="Test Title",
        notes="Some notes",
        genre="Fantasy",
        tone="Epic",
        audience="Young Adult",
        length="Novel",
    )
    mock_outline_data = {
        "chapters": [
            {"chapter_number": 1, "title": "Chapter 1", "brief": "Intro"},
            {"chapter_number": 2, "title": "Chapter 2", "brief": "Conflict"},
        ]
    }
    mock_book_dict = {
        "id": str(uuid4()),
        "title": "Test Title",
        "initial_notes": "Some notes",
        "outline": mock_outline_data,
        "outline_status": StageStatus.OUTLINE_REVIEW.value,
        "final_review_notes_status": StageStatus.PENDING_REVIEW.value,
        "phase": "outline",
        "human_notes": None,
        "genre": "Fantasy",
        "tone": "Epic",
        "audience": "Young Adult",
        "length": "Novel",
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
    }

    with patch("app.modules.generation.service.db_service") as mock_db, \
         patch("app.modules.generation.service.ai_service") as mock_ai:
        mock_ai.generate_outline.return_value = type('Obj', (), {'dict': lambda: mock_outline_data})()
        mock_db.create_book_with_outline.return_value = mock_book_dict

        # Act
        result = gen_service.generate_outline(payload)

        # Assert
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
        mock_db.create_book_with_outline.assert_called_once()


def test_generate_chapter_success():
    # Arrange
    chapter_id = uuid4()
    payload = GenerateChapterRequest(chapter_id=chapter_id)
    mock_chapter = {
        "id": str(chapter_id),
        "book_id": str(uuid4()),
        "chapter_number": 3,
        "title": "Chapter 3",
        "content": None,
        "summary": None,
        "status": StageStatus.NO_NOTES_NEEDED.value,
        "human_notes": None,
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
    }
    mock_book = {
        "id": str(chapter_id),
        "title": "Test Book",
        "outline": {
            "chapters": [
                {"chapter_number": 3, "title": "Chapter 3", "brief": "Details"},
            ]
        },
    }
    mock_outline_obj = type('Obj', (), {'chapters': [type('Chap', (), {'chapter_number': 3, 'title': 'Chapter 3', 'brief': 'Details'})]})
    mock_chapter_content = "Generated chapter text."
    mock_summary = "Summary of chapter."

    with patch("app.modules.generation.service.db_service") as mock_db, \
         patch("app.modules.generation.service.ai_service") as mock_ai:
        mock_db.get_chapter.return_value = mock_chapter
        mock_db.get_book.return_value = mock_book
        mock_ai.generate_chapter.return_value = mock_chapter_content
        mock_ai.summarize_chapter.return_value = mock_summary
        # Mock OutlineData.model_validate to return our mock object
        with patch("app.modules.generation.service.OutlineData") as mock_outline_cls:
            mock_outline_cls.model_validate.return_value = mock_outline_obj
            mock_db.update_chapter.return_value = {
                **mock_chapter,
                "content": mock_chapter_content,
                "summary": mock_summary,
                "status": "pending_review",
            }

            # Act
            result = gen_service.generate_chapter(payload)

            # Assert
            assert isinstance(result, ChapterResponse)
            assert result.chapter_id == chapter_id
            assert result.content == mock_chapter_content
            assert result.summary == mock_summary
            mock_db.get_chapter.assert_called_once_with(chapter_id)
            mock_db.get_book.assert_called_once()
            mock_ai.generate_chapter.assert_called_once()
            mock_ai.summarize_chapter.assert_called_once()
            mock_db.update_chapter.assert_called_once()
