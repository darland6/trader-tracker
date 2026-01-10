"""Notification API routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

from api.database import (
    get_active_notifications,
    get_notification_by_id,
    get_notification_count,
    create_notification,
    dismiss_notification,
    snooze_notification,
    mark_notification_read
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationCreate(BaseModel):
    type: str
    title: str
    message: Optional[str] = None
    severity: str = "info"
    data: Optional[dict] = None
    action_type: Optional[str] = None
    action_data: Optional[dict] = None


class SnoozeRequest(BaseModel):
    hours: int = 24


@router.get("")
async def list_notifications(include_snoozed: bool = False):
    """Get all active notifications."""
    notifications = get_active_notifications(include_snoozed=include_snoozed)
    counts = get_notification_count()
    return {
        "notifications": notifications,
        "counts": counts
    }


@router.get("/count")
async def notification_counts():
    """Get notification counts by severity."""
    return get_notification_count()


@router.get("/{notification_id}")
async def get_notification(notification_id: int):
    """Get a single notification."""
    notification = get_notification_by_id(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.post("")
async def create_new_notification(notification: NotificationCreate):
    """Create a new notification."""
    notification_id = create_notification(
        type=notification.type,
        title=notification.title,
        message=notification.message,
        severity=notification.severity,
        data=notification.data,
        action_type=notification.action_type,
        action_data=notification.action_data
    )
    return {"success": True, "notification_id": notification_id}


@router.post("/{notification_id}/dismiss")
async def dismiss_notification_route(notification_id: int):
    """Dismiss a notification."""
    success = dismiss_notification(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}


@router.post("/{notification_id}/snooze")
async def snooze_notification_route(notification_id: int, request: SnoozeRequest):
    """Snooze a notification for a specified number of hours."""
    until = (datetime.now() + timedelta(hours=request.hours)).isoformat()
    success = snooze_notification(notification_id, until)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True, "snoozed_until": until}


@router.post("/{notification_id}/read")
async def mark_read_route(notification_id: int):
    """Mark a notification as read."""
    success = mark_notification_read(notification_id)
    return {"success": success}


@router.post("/check")
async def run_alert_checks():
    """Run all alert checks and create notifications."""
    from api.services.alerts import run_all_alert_checks
    results = run_all_alert_checks()
    return {
        "success": True,
        "results": results,
        "message": f"Created {results['total_created']} new notifications"
    }


@router.get("/scheduler/status")
async def get_scheduler_status():
    """Get background scheduler status."""
    from api.services.scheduler import scheduler
    is_open, session = scheduler.is_market_hours()
    return {
        "running": scheduler.running,
        "market_open": is_open,
        "session": session,
        "active_tasks": list(scheduler.tasks.keys())
    }
