from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.models import (
    TemplateCreateRequest,
    TemplateResponse,
    TemplateUpdateRequest,
    TemplateListResponse,
)
from app.services import db_service

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(payload: TemplateCreateRequest):
    """Create a new outline template."""
    try:
        template_data = {
            "name": payload.name,
            "description": payload.description,
            "template_json": payload.template_json,
            "category": payload.category,
            "is_public": payload.is_public,
            "created_by": str(payload.created_by) if payload.created_by else None,
        }

        # Remove None values to avoid inserting NULLs unnecessarily
        template_data = {k: v for k, v in template_data.items() if v is not None}

        created = db_service.create_template(template_data)
        return TemplateResponse.model_validate(created)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create template: {exc}",
        ) from exc


@router.get("", response_model=TemplateListResponse)
def list_templates(category: str | None = None, public_only: bool = True):
    """List outline templates with optional filtering."""
    try:
        templates = db_service.list_templates(category=category, public_only=public_only)
        return TemplateListResponse(templates=[TemplateResponse.model_validate(t) for t in templates])
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list templates: {exc}",
        ) from exc


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(template_id: UUID):
    """Get a specific outline template by ID."""
    try:
        template = db_service.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return TemplateResponse.model_validate(template)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve template: {exc}",
        ) from exc


@router.patch("/{template_id}", response_model=TemplateResponse)
def update_template(template_id: UUID, payload: TemplateUpdateRequest):
    """Update an existing outline template."""
    try:
        # Get existing template first
        existing = db_service.get_template(template_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Template not found")

        # Prepare update data (only include fields that were provided)
        update_data = payload.model_dump(exclude_unset=True)

        # Handle special cases
        if update_data.get("created_by") is not None:
            update_data["created_by"] = str(update_data["created_by"])

        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}

        if not update_data:
            # No changes to make
            return TemplateResponse.model_validate(existing)

        updated = db_service.update_template(template_id, update_data)
        if not updated:
            raise HTTPException(status_code=404, detail="Template not found")

        return TemplateResponse.model_validate(updated)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update template: {exc}",
        ) from exc


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: UUID):
    """Delete an outline template."""
    try:
        deleted = db_service.delete_template(template_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Template not found")
        return None
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete template: {exc}",
        ) from exc