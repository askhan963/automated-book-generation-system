from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Any, Optional

class TemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    template_json: dict[str, Any]  # Should match OutlineData structure
    category: Optional[str] = None
    is_public: bool = True
    created_by: Optional[UUID] = None

class TemplateResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    template_json: dict[str, Any]
    category: Optional[str] = None
    is_public: bool
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    template_json: Optional[dict[str, Any]] = None
    category: Optional[str] = None
    is_public: Optional[bool] = None

class TemplateListResponse(BaseModel):
    templates: list[TemplateResponse]