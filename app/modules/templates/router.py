from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from app.modules.templates.schemas import (
    TemplateCreateRequest,
    TemplateResponse,
    TemplateUpdateRequest,
    TemplateListResponse,
)
from app.modules.templates.service import (
    create_template,
    list_templates,
    get_template,
    update_template,
    delete_template,
)

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template_endpoint(payload: TemplateCreateRequest):
    return create_template(payload)


@router.get("", response_model=TemplateListResponse)
def list_templates_endpoint(category: str | None = None, public_only: bool = True):
    return list_templates(category=category, public_only=public_only)


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template_endpoint(template_id: UUID):
    return get_template(template_id)


@router.patch("/{template_id}", response_model=TemplateResponse)
def update_template_endpoint(template_id: UUID, payload: TemplateUpdateRequest):
    return update_template(template_id, payload)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template_endpoint(template_id: UUID):
    delete_template(template_id)
    return None