import json
from typing import Any

from openai import OpenAI

from app.core.config import get_settings
from app.models import OutlineChapterItem, OutlineData

EXPERT_AUTHOR_SYSTEM = (
    "You are an expert author with mastery of narrative structure, voice, and pacing. "
    "Write vivid, cohesive prose that honors established plot threads and character arcs. "
    "Maintain tonal consistency with prior chapters."
)

SUMMARIZER_SYSTEM = (
    "You are an expert author and editor. "
    "Produce concise, accurate summaries that preserve plot continuity for future chapters."
)

PreviousSummary = str | dict[str, Any]


def get_openai_client(client: OpenAI | None = None) -> OpenAI:
    """Return a provided client or build one from application settings."""
    if client is not None:
        return client
    settings = get_settings()
    kwargs: dict[str, str] = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


def _complete(
    system: str,
    user: str,
    *,
    client: OpenAI | None = None,
    max_tokens: int | None = None,
) -> str:
    settings = get_settings()
    kwargs: dict[str, Any] = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.7,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    response = get_openai_client(client).chat.completions.create(**kwargs)
    return (response.choices[0].message.content or "").strip()


def format_previous_summaries(previous_summaries: list[PreviousSummary]) -> str:
    """Turn stored summaries into prompt context for continuity."""
    if not previous_summaries:
        return "This is the first chapter; no prior context."

    blocks: list[str] = []
    for index, entry in enumerate(previous_summaries, start=1):
        if isinstance(entry, str):
            blocks.append(f"Prior chapter {index}:\n{entry}")
            continue
        chapter_number = entry.get("chapter_number", index)
        chapter_title = entry.get("title", f"Chapter {chapter_number}")
        summary = entry.get("summary", "")
        blocks.append(f"Chapter {chapter_number} — {chapter_title}:\n{summary}")

    return "\n\n".join(blocks)


def generate_chapter(
    title: str,
    outline: OutlineChapterItem,
    previous_summaries: list[PreviousSummary],
    chapter_notes: str | None = None,
    genre: str | None = None,
    tone: str | None = None,
    audience: str | None = None,
    length: str | None = None,
    *,
    client: OpenAI | None = None,
) -> str:
    """
    Generate a single chapter using prior summaries for continuity.

    Args:
        title: Book title.
        outline: Current chapter outline (number, title, brief).
        previous_summaries: Summaries from earlier chapters (strings or dicts).
        chapter_notes: Optional human revision notes.
        client: Optional pre-configured OpenAI SDK client.

    Returns:
        Full chapter prose.
    """
    prior_context = format_previous_summaries(previous_summaries)
    notes_block = f"\n\nRevision notes from editor:\n{chapter_notes}" if chapter_notes else ""

    # Build the base prompt with required info
    user_prompt = (
        f"Book title: {title}\n"
        f"Chapter {outline.chapter_number}: {outline.title}\n"
        f"Chapter outline:\n{outline.brief}\n\n"
        f"--- Previous chapters (for continuity) ---\n{prior_context}"
        f"{notes_block}\n"
    )
    # Append optional style/tone information if provided
    style_parts = []
    if genre:
        style_parts.append(f"Genre: {genre}")
    if tone:
        style_parts.append(f"Tone: {tone}")
    if audience:
        style_parts.append(f"Target audience: {audience}")
    if length:
        style_parts.append(f"Desired length: {length}")
    if style_parts:
        user_prompt += "\n--- Style & Tone ---\n" + "\n".join(style_parts) + "\n"
    # Final instruction
    user_prompt += (
        "\nWrite the complete chapter (approximately 800–1200 words). "
        "Return only the chapter text."
    )

    # Generate chapter content
    content = _complete(EXPERT_AUTHOR_SYSTEM, user_prompt, client=client)
    # Run simple moderation check – will raise HTTPException on failure
    from app.services.moderation_service import validate_content
    validate_content(content)
    return content


def summarize_chapter(content: str, *, client: OpenAI | None = None) -> str:
    """
    Summarize chapter content in exactly three sentences for context chaining.

    Args:
        content: Full chapter text.
        client: Optional pre-configured OpenAI SDK client.

    Returns:
        A three-sentence summary string.
    """
    user_prompt = (
        "Summarize the following chapter in exactly three sentences. "
        "Capture key plot events, character developments, and hooks for the next chapter. "
        "Return only the three sentences.\n\n"
        f"{content[:12000]}"
    )
    summary = _complete(SUMMARIZER_SYSTEM, user_prompt, client=client, max_tokens=300)

    # Perform quality checks on the summary
    _validate_summary_quality(summary, content)

    return summary


def _validate_summary_quality(summary: str, content: str) -> None:
    """
    Perform quality checks on a generated summary.

    Args:
        summary: The generated summary to validate
        content: The original chapter content (for length comparison)

    Raises:
        HTTPException: If the summary fails quality checks
    """
    from fastapi import HTTPException

    # Check 1: Summary should not be empty or just whitespace
    if not summary or not summary.strip():
        raise HTTPException(
            status_code=500,
            detail="Generated summary is empty"
        )

    # Check 2: Summary should be reasonable length (10-500 characters)
    if len(summary.strip()) < 10:
        raise HTTPException(
            status_code=500,
            detail=f"Generated summary is too short: {len(summary.strip())} characters"
        )

    if len(summary.strip()) > 500:
        raise HTTPException(
            status_code=500,
            detail=f"Generated summary is too long: {len(summary.strip())} characters"
        )

    # Check 3: Summary should not be mostly repetitive content
    # Simple check: if the same word makes up >50% of the summary, it's likely low quality
    words = summary.lower().split()
    if len(words) > 3:
        from collections import Counter
        word_counts = Counter(words)
        most_common_count = word_counts.most_common(1)[0][1]
        if most_common_count / len(words) > 0.5:
            raise HTTPException(
                status_code=500,
                detail="Generated summary appears to be overly repetitive"
            )

    # Check 4: Summary should be substantially shorter than the original content
    # (except for very short content)
    if len(content.strip()) > 100 and len(summary.strip()) > len(content.strip()) * 0.5:
        raise HTTPException(
            status_code=500,
            detail="Generated summary is not sufficiently shorter than the original content"
        )


def check_openrouter_health() -> tuple[str, str | None]:
    """Lightweight LLM ping. Returns (status, error_detail)."""
    try:
        content = _complete(
            EXPERT_AUTHOR_SYSTEM,
            "Reply with exactly: OK",
            max_tokens=10,
        )
        if not content:
            return "error", "Empty response from LLM"
        return "ok", None
    except Exception as exc:
        return "error", str(exc)


def generate_outline(title: str, initial_notes: str | None, genre: str | None = None, tone: str | None = None, audience: str | None = None, length: str | None = None) -> OutlineData:
    notes_block = f"\nAuthor notes:\n{initial_notes}" if initial_notes else ""
    system = (
        "You are an expert book planner. Return ONLY valid JSON with this shape: "
        '{"chapters": [{"chapter_number": 1, "title": "...", "brief": "..."}]} '
        "Provide 5-8 chapters with clear briefs."
    )
    user = f"Create a detailed book outline for: {title}{notes_block}"
    raw = _complete(system, user)

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    data = json.loads(cleaned)
    outline = OutlineData.model_validate(data)

    # Add style/tone information to each chapter brief if provided
    if any([genre, tone, audience, length]):
        style_parts = []
        if genre:
            style_parts.append(f"Genre: {genre}")
        if tone:
            style_parts.append(f"Tone: {tone}")
        if audience:
            style_parts.append(f"Target audience: {audience}")
        if length:
            style_parts.append(f"Desired length: {length}")

        style_info = "\n--- Style & Tone ---\n" + "\n".join(style_parts)

        # Update each chapter's brief to include style/tone information
        for chapter in outline.chapters:
            chapter.brief = f"{chapter.brief}\n{style_info}"

    return outline
