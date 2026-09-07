# Notifications and Background Tasks Design

## Current implementation

- `src/notifications/notifier.py` sends SMTP+STARTTLS email and Telegram Bot API messages.
- `build_report_from_wagon()` calculates class counts and 25/50 kg estimated weight from persisted events.
- `src/tasks/celery_app.py` configures Celery/Redis.
- `src/tasks/tasks.py` defines clip, notification, report, dashboard-update, and clip-cleanup tasks with logging/retry behavior where configured.

## Known defect

The Celery clip task currently calls a missing method. Do not assume queued clip processing works until an explicit repair change is implemented and tested.
