"""
Celery distributed task queue for Bag Counter Edge.

Handles:
- Async clip processing
- Notification delivery
- Model inference (optional batch)
- Database operations
- Report generation
"""
from .celery_app import celery_app
from .tasks import (
    process_clip_task,
    send_notification_task,
    generate_report_task,
    update_dashboard_task,
)

__all__ = [
    "celery_app",
    "process_clip_task",
    "send_notification_task",
    "generate_report_task",
    "update_dashboard_task",
]
