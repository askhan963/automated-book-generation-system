from typing import Optional

from pydantic import BaseModel, Field

from app.models import (
    ApiKeyCreateResponse,
    ApiKeyItemResponse,
    ApiKeyListResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
