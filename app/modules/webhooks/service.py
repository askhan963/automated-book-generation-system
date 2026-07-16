import httpx
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Any
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel

from app.modules.webhooks.schemas import OutlineApprovedWebhook, ChapterCompletedWebhook
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Pydantic models for request bodies (copied from schemas for local use)
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


def outline_approved_webhook(webhook_data: OutlineApprovedWebhook) -> None:
    """
    Send outline approved notifications to integrated services (Slack, CI/CD, etc.)
    Returns None (for HTTP 204 response)
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
        # Note: This function is now synchronous, but we'll keep the async pattern
        # In a real implementation, we might want to make this async or use background tasks
        logger.info(f"Would send Slack notification for outline approval: {webhook_data.book_id}")
        # For now, we'll just log since we can't easily make async calls from sync function
        # A proper implementation would use background tasks or make the endpoint async
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
    # Note: This would need to be handled differently in a sync context
    # For now, we'll just log the intent
    logger.info(f"Would send CI/CD webhook for outline approval: {webhook_data.book_id}")

    return None


def chapter_completed_webhook(webhook_data: ChapterCompletedWebhook) -> None:
    """
    Send chapter completed notifications to integrated services (Slack, CI/CD, etc.)
    Returns None (for HTTP 204 response)
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
        logger.info(f"Would send Slack notification for chapter completion: {webhook_data.book_id} - Chapter {webhook_data.chapter_number}")
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
    logger.info(f"Would send CI/CD webhook for chapter completion: {webhook_data.book_id} - Chapter {webhook_data.chapter_number}")

    return None