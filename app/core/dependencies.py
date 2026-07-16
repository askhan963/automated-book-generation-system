"""
Core dependencies for the Automated Book Generation System.
Provides dependency injection for external services and clients.
"""
from functools import lru_cache
from typing import Optional

from supabase import Client, create_client
from openai import OpenAI

from app.core.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    """Get Supabase client instance."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)


@lru_cache
def get_openai_client() -> OpenAI:
    """Get OpenAI/OpenRouter client instance."""
    settings = get_settings()
    kwargs: dict[str, str] = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)