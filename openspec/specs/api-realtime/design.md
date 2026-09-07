# API and Realtime Design

## Current implementation

- `src/api/app.py` uses FastAPI and includes monitoring routes from `src/monitoring/metrics.py`.
- Rate limiting uses SlowAPI with an IP-based default rate.
- JWT validation decodes HS256 tokens using `API_SECRET_KEY` and returns the `sub` claim as the current user.
- Protected Celery task triggers cover notifications, report generation, and dashboard update.
- `src/websocket/manager.py` holds in-process WebSocket subscriptions and helpers for dashboard/events/alerts broadcasts.
- Live MJPEG streaming creates a separate `CameraStream` singleton for API video feed.

## Known contract gaps

- OAuth2 metadata points to `/api/v1/auth/login`, but no login/token issuer route exists.
- `/api/v1/stats/today` currently aggregates the entire DB and is not date-filtered.
- CORS currently allows all origins.
