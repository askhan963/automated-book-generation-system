from typing import Annotated

from fastapi import Depends

from app.modules.ai.service import get_openai_client
from openai import OpenAI


def get_openai_client_dependency() -> OpenAI:
    """FastAPI dependency that provides an OpenAI client."""
    return get_openai_client()


# Optional: exports for convenience
OpenAIDepends = Annotated[OpenAI, Depends(get_openai_client_dependency)]