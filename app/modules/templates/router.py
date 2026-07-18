from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserResponse
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
def create_template_endpoint(
    payload: TemplateCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    if payload.created_by is None:
        payload = payload.model_copy(update={"created_by": current_user.id})
    return create_template(payload)


@router.get("", response_model=TemplateListResponse)
def list_templates_endpoint(
    category: str | None = None,
    public_only: bool = True,
    current_user: UserResponse = Depends(get_current_user),
):
    return list_templates(category=category, public_only=public_only)


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template_endpoint(
    template_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
):
    return get_template(template_id)


@router.patch("/{template_id}", response_model=TemplateResponse)
def update_template_endpoint(
    template_id: UUID,
    payload: TemplateUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    return update_template(template_id, payload)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template_endpoint(
    template_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
):
    delete_template(template_id)
    return None
