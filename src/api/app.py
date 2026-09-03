"""
FastAPI service for local stats and health.
Now includes WebSocket support, Celery task integration, and Prometheus metrics.
"""
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from typing import Optional, AsyncGenerator
import asyncio
import time
import io
import cv2
import numpy as np

from src.db.models import SessionLocal, Wagon, BagEvent, Shift
from src.config import settings
from src.websocket.manager import get_ws_manager
from src.tasks.tasks import (
    send_notification_task,
    generate_report_task,
    update_dashboard_task,
)
from src.monitoring.metrics import (
    router as metrics_router,
    record_api_request,
    record_bag_detected,
    record_detection_confidence,
    update_connected_clients,
    BAG_COUNT_TOTAL,
)
from src.capture.camera_stream import CameraStream

app = FastAPI(title="Bag Counter Edge API")

# Include Prometheus metrics router
app.include_router(metrics_router)

# Rate limiting setup
slowapi_limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.API_RATE_LIMIT_PER_MINUTE}/minute"],
)
app.state.limiter = slowapi_limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[str]:
    """Get current authenticated user from JWT token."""
    if not token:
        return None
    # Validate JWT token using API_SECRET_KEY
    try:
        from jose import jwt, JWTError
        payload = jwt.decode(token, settings.API_SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except (JWTError, Exception):
        return None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/wagons/active")
def active_wagon(db: Session = Depends(get_db)):
    wagon = db.query(Wagon).filter_by(is_active=True).first()
    if not wagon:
        return {"detail": "No active wagon"}
    return {
        "id": wagon.id,
        "number": wagon.wagon_number,
        "started_at": wagon.started_at,
    }


@app.get("/api/v1/stats/today")
def today_stats(db: Session = Depends(get_db)):
    # Simplified: count all bags in DB
    total = db.query(BagEvent).count()
    by_class = {}
    for cls in ["25kg", "50kg", "empty"]:
        by_class[cls] = db.query(BagEvent).filter_by(bag_class=cls).count()
    return {"total_counted": total, "by_class": by_class}


# ── WebSocket Endpoint ──────────────────────────────────────────────────────
@app.websocket("/ws/{channel}")
async def websocket_endpoint(websocket: WebSocket, channel: str = "general"):
    """
    WebSocket endpoint for real-time updates.
    
    Channels:
    - general: All messages
    - dashboard: Stats updates
    - events: Bag detection events
    - alerts: System alerts
    """
    ws_manager = get_ws_manager()
    await ws_manager.connect(websocket, channel)
    try:
        while True:
            # Keep connection alive, receive messages from client
            data = await websocket.receive_text()
            # Handle client commands (subscribe/unsubscribe)
            try:
                import json
                msg = json.loads(data)
                if msg.get("action") == "subscribe":
                    await ws_manager.subscribe(websocket, msg.get("channel"))
                elif msg.get("action") == "unsubscribe":
                    await ws_manager.unsubscribe(websocket, msg.get("channel"))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)


# ── Task Endpoints (Celery Integration) ─────────────────────────────────────
@app.post("/api/v1/tasks/send-notification")
async def trigger_notification(
    request: Request,
    event_type: str = None,
    data: dict = None,
    channels: Optional[list] = None,
    current_user: str = Depends(get_current_user)
):
    """Trigger a notification via Celery task."""
    import json
    # Handle both query params and JSON body
    if event_type is None or data is None:
        try:
            body = await request.json()
            event_type = body.get("event_type")
            data = body.get("data")
            channels = body.get("channels", channels)
        except:
            pass
    
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    if not event_type or data is None:
        raise HTTPException(status_code=400, detail="event_type and data are required")
    
    task = send_notification_task.delay(event_type, data, channels)
    return {"task_id": task.id, "status": "queued"}


@app.post("/api/v1/tasks/generate-report/{wagon_id}")
async def trigger_report(
    wagon_id: int,
    current_user: str = Depends(get_current_user)
):
    """Generate a wagon report via Celery task."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    task = generate_report_task.delay(wagon_id)
    return {"task_id": task.id, "status": "queued"}


@app.post("/api/v1/tasks/update-dashboard")
async def trigger_dashboard_update(
    wagon_id: Optional[int] = None,
    current_user: str = Depends(get_current_user)
):
    """Update dashboard stats via Celery task (non-blocking)."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    task = update_dashboard_task.delay(wagon_id)
    return {"task_id": task.id, "status": "queued"}


# ── Broadcast Helpers ──────────────────────────────────────────────────────
async def broadcast_bag_event(event_data: dict):
    """Broadcast a bag detection event to connected clients."""
    ws_manager = get_ws_manager()
    await ws_manager.broadcast_event(event_data)


async def broadcast_stats(stats: dict):
    """Broadcast updated statistics to dashboard clients."""
    ws_manager = get_ws_manager()
    await ws_manager.broadcast_stats(stats)


async def broadcast_alert(alert_data: dict):
    """Broadcast an alert to all connected clients."""
    ws_manager = get_ws_manager()
    await ws_manager.broadcast_alert(alert_data)


# ── Video Streaming Endpoint (MJPEG) ────────────────────────────────────────
_camera_stream: Optional[CameraStream] = None

def get_camera_stream() -> CameraStream:
    """Get or create camera stream instance."""
    global _camera_stream
    if _camera_stream is None or not _camera_stream._running:
        _camera_stream = CameraStream(
            source=settings.PRIMARY_STREAM_URL,
            name="video_feed",
        )
        _camera_stream.start()
    return _camera_stream


@app.get("/api/v1/video/stream")
async def video_stream():
    """
    MJPEG video stream endpoint for live camera feed.
    
    Usage in browser/Streamlit:
    <img src="/api/v1/video/stream" />
    """
    from starlette.responses import StreamingResponse
    
    async def generate_frames():
        camera = get_camera_stream()
        while True:
            ok, frame, ts = camera.read()
            if ok and frame is not None:
                # Encode frame as JPEG
                _, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
                )
            else:
                # Send placeholder frame if camera unavailable
                placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(placeholder, "No Signal", (200, 240), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                _, buffer = cv2.imencode(".jpg", placeholder, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
                )
            await asyncio.sleep(0.033)  # ~30 FPS
    
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache"}
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup camera stream on shutdown."""
    global _camera_stream
    if _camera_stream:
        _camera_stream.stop()
        _camera_stream = None
