"""Simple content moderation service.

This placeholder implementation uses a hard‑coded blacklist of prohibited words. It provides a
`validate_content` function that raises an HTTPException with status 400 when disallowed
content is detected. In a real system you would replace this with a more sophisticated
service (e.g., OpenAI moderation endpoint, profanity‑filter library, etc.).
"""

from fastapi import HTTPException

# Example blacklist – extend as needed
BLACKLIST = {"badword", "nastyphrase", "offensive"}


def validate_content(text: str) -> None:
    """Raise HTTPException if any blacklisted term appears in `text`.

    The check is case‑insensitive and looks for whole‑word matches.
    """
    lowered = text.lower()
    for word in BLACKLIST:
        if word in lowered:
            raise HTTPException(
                status_code=400,
                detail=f"Content contains disallowed term: '{word}'",
            )
    # No blacklisted term – content is acceptable
    return None
