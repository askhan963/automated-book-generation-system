from fastapi import APIRouter, HTTPException, status
from uuid import UUID
from typing import Dict, Any

from app.modules.webhooks.schemas import OutlineApprovedWebhook, ChapterCompletedWebhook
from app.modules.webhooks.service import outline_approved_webhook, chapter_completed_webhook

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/outline-approved", status_code=status.HTTP_204_NO_CONTENT)
async def outline_approved_webhook_endpoint(webhook_data: OutlineApprovedWebhook):
    """
    Send outline approved notifications to integrated services (Slack, CI/CD, etc.)
    """
    outline_approved_webhook(webhook_data)
    return None


@router.post("/chapter-completed", status_code=status.HTTP_204_NO_CONTENT)
async def chapter_completed_webhook_endpoint(webhook_data: ChapterCompletedWebhook):
    """
    Send chapter completed notifications to integrated services (Slack, CI/CD, etc.)
    """
    chapter_completed_webhook(webhook_data)
    return None