from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
from uuid import UUID

from app.core.config import get_settings
import httpx
import json
import logging
from datetime import datetime

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


async def send_cicd_webhook(event_type: str, data: Dict[str, Any]):
    """Send webhook notifications to CI/CD systems."""
    settings = get_settings()
    cicd_webhook_url = getattr(settings, 'cicd_webhook_url', None)

    if not cicd_webhook_url:
        logger.debug("CI/CD webhook URL not configured")
        return

    # Prepare payload for CI/CD systems
    payload = {
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": data
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                cicd_webhook_url,
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            logger.info(f"CI/CD webhook sent for {event_type}")
    except Exception as e:
        logger.error(f"Failed to send CI/CD webhook: {e}")


class OutlineApprovedWebhook(BaseModel):
    book_id: UUID
    book_title: str
    outline_data: Dict[str, Any]
    approved_by: Optional[str] = None
    approval_notes: Optional[str] = None


class ChapterCompletedWebhook(BaseModel):
    book_id: UUID
    book_title: str
    chapter_number: int
    chapter_title: str
    chapter_summary: Optional[str] = None
    completed_by: Optional[str] = None


@router.post("/outline-approved", status_code=status.HTTP_204_NO_CONTENT)
async def outline_approved_webhook(webhook_data: OutlineApprovedWebhook):
    """
    Send outline approved notifications to integrated services (Slack, CI/CD, etc.)
    """
    settings = get_settings()

    # Prepare Slack message
    slack_message = {
        "text": f"📋 *Outline Approved*",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Outline Approved*\n• *Book*: {webhook_data.book_title}\n• *ID*: {webhook_data.book_id}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Approved by: {webhook_data.approved_by or 'System'}"
                    }
                ]
            }
        ]
    }

    if webhook_data.approval_notes:
        slack_message["blocks"].append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Approval Notes:*\n{webhook_data.approval_notes}"
            }
        })

    # Send to Slack if webhook URL is configured
    slack_webhook_url = getattr(settings, 'slack_webhook_url', None)
    if slack_webhook_url:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    slack_webhook_url,
                    json=slack_message,
                    timeout=10.0
                )
                response.raise_for_status()
                logger.info(f"Slack notification sent for outline approval: {webhook_data.book_id}")
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
    else:
        logger.debug("Slack webhook URL not configured")

    # Prepare data for CI/CD webhook
    cicd_data = {
        "book_id": str(webhook_data.book_id),
        "book_title": webhook_data.book_title,
        "outline_data": webhook_data.outline_data,
        "approved_by": webhook_data.approved_by or "System",
        "approval_notes": webhook_data.approval_notes,
        "event": "outline_approved"
    }

    # Send to CI/CD if webhook URL is configured
    await send_cicd_webhook("outline_approved", cicd_data)

    return None


@router.post("/chapter-completed", status_code=status.HTTP_204_NO_CONTENT)
async def chapter_completed_webhook(webhook_data: ChapterCompletedWebhook):
    """
    Send chapter completed notifications to integrated services (Slack, CI/CD, etc.)
    """
    settings = get_settings()

    # Prepare Slack message
    slack_message = {
        "text": f"📖 *Chapter Completed*",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Chapter Completed*\n• *Book*: {webhook_data.book_title}\n• *Chapter*: {webhook_data.chapter_number} - {webhook_data.chapter_title}\n• *Book ID*: {webhook_data.book_id}"
                }
            }
        ]
    }

    if webhook_data.chapter_summary:
        # Truncate summary if too long for Slack
        summary = webhook_data.chapter_summary
        if len(summary) > 300:
            summary = summary[:297] + "..."
        slack_message["blocks"].append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Summary:*\n{summary}"
            }
        })

    # Send to Slack if webhook URL is configured
    slack_webhook_url = getattr(settings, 'slack_webhook_url', None)
    if slack_webhook_url:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    slack_webhook_url,
                    json=slack_message,
                    timeout=10.0
                )
                response.raise_for_status()
                logger.info(f"Slack notification sent for chapter completion: {webhook_data.book_id} - Chapter {webhook_data.chapter_number}")
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
    else:
        logger.debug("Slack webhook URL not configured")

    # Prepare data for CI/CD webhook
    cicd_data = {
        "book_id": str(webhook_data.book_id),
        "book_title": webhook_data.book_title,
        "chapter_number": webhook_data.chapter_number,
        "chapter_title": webhook_data.chapter_title,
        "chapter_summary": webhook_data.chapter_summary,
        "completed_by": webhook_data.completed_by or "System",
        "event": "chapter_completed"
    }

    # Send to CI/CD if webhook URL is configured
    await send_cicd_webhook("chapter_completed", cicd_data)

    return None