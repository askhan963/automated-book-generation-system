from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    supabase_url: str
    supabase_key: str

    @field_validator("supabase_url", "supabase_key", "openai_api_key", mode="before")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value
    openai_api_key: str
    openai_base_url: str | None = "https://openrouter.ai/api/v1"
    openai_model: str = "openai/gpt-4o-mini"

    # JWT settings for auth
    jwt_secret: str
    jwt_expires_minutes: int = 30

    # Slack webhook URL for notifications
    slack_webhook_url: Optional[str] = None

    # CI/CD webhook URL for notifications (GitHub Actions, GitLab CI, Jenkins, etc.)
    cicd_webhook_url: Optional[str] = None

    # When true, outline/chapters pause at pending_review for human approval
    require_human_review: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
