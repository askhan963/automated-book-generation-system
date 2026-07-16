import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from app.modules.ai import service as ai_service


def test_generate_chapter_success():
    # Mock internal functions
    with patch("app.modules.ai.service._complete") as mock_complete, \
         patch("app.services.moderation_service.validate_content") as mock_validate, \
         patch("app.modules.ai.service._validate_summary_quality") as mock_validate_summary:
        mock_complete.side_effect = [
            "Chapter text content.",   # first call for chapter generation
            "Three sentence summary." # second call for summarize_chapter inside? Actually generate_chapter does not call summarize.
        ]
        # generate_chapter calls _complete once, then validate_content, then returns content
        result = ai_service.generate_chapter(
            title="Test Book",
            outline=type('Obj', (), {'chapter_number': 1, 'title': 'Chapter 1', 'brief': 'Brief'})(),
            previous_summaries=[],
            chapter_notes=None,
            genre="Fantasy",
            tone="Epic",
            audience="YA",
            length="Novel",
        )
        assert result == "Chapter text content."
        mock_complete.assert_called_once()
        # validate_content called
        mock_validate.assert_called_once_with("Chapter text content.")


def test_generate_chapter_moderation_fails():
    with patch("app.modules.ai.service._complete") as mock_complete, \
         patch("app.modules.ai.service.validate_content") as mock_validate:
        mock_complete.return_value = "Bad content"
        mock_validate.side_effect = HTTPException(status_code=400, detail="Bad content")
        with pytest.raises(HTTPException):
            ai_service.generate_chapter(
                title="Test",
                outline=type('Obj', (), {'chapter_number': 1, 'title': 'Ch', 'brief': 'B'})(),
                previous_summaries=[],
                chapter_notes=None,
            )


def test_summarize_chapter_success():
    with patch("app.modules.ai.service._complete") as mock_complete, \
         patch("app.modules.ai.service._validate_summary_quality") as mock_validate:
        mock_complete.return_value = "This is a summary. It has two sentences. Actually three."
        # _validate_summary_quality does not return anything
        result = ai_service.summarize_chapter("Some long chapter text.")
        assert result == "This is a summary. It has two sentences. Actually three."
        mock_called = mock_complete.call_args
        assert mock_called is not None
        # Validate prompt includes text
        assert "Summarize the following chapter" in mock_called.kwargs["user"]
        mock_validate.assert_called_once()


def test_generate_outline_success():
    import json
    with patch("app.modules.ai.service._complete") as mock_complete:
        # Return JSON string wrapped in markdown
        mock_complete.return_value = """```json
{
  "chapters": [
    {"chapter_number": 1, "title": "Start", "brief": "Beginning"},
    {"chapter_number": 2, "title": "Middle", "brief": "Conflict"}
  ]
}
```"""
        result = ai_service.generate_outline(
            title="Test Book",
            initial_notes="Make it exciting",
            genre="Sci-Fi",
            tone="Dark",
            audience="Adult",
            length="Short",
        )
        # Validate that result is an OutlineData with correct chapters
        assert len(result.chapters) == 2
        assert result.chapters[0].title == "Start"
        assert result.chapters[1].title == "Middle"
        # Check that style info added to brief
        assert "Genre: Sci-Fi" in result.chapters[0].brief
        assert "Tone: Dark" in result.chapters[0].brief
        assert "Target audience: Adult" in result.chapters[0].brief
        assert "Desired length: Short" in result.chapters[0].brief


def test_check_openrouter_health_ok():
    with patch("app.modules.ai.service._complete") as mock_complete:
        mock_complete.return_value = "OK"
        status, detail = ai_service.check_openrouter_health()
        assert status == "ok"
        assert detail is None
        mock_complete.assert_called_once_with(
            "You are an expert author with mastery of narrative structure, voice, and pacing. "
            "Write vivid, cohesive prose that honors established plot threads and character arcs. "
            "Maintain tonal consistency with prior chapters.",
            "Reply with exactly: OK",
            max_tokens=10,
        )


def test_check_openrouter_health_error():
    with patch("app.modules.ai.service._complete") as mock_complete:
        mock_complete.side_effect = Exception("Network error")
        status, detail = ai_service.check_openrouter_health()
        assert status == "error"
        assert "Network error" in detail