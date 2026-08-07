# Bag Counter Edge — Autonomous CV System for Flour Bag Loading

## 🚀 New Features (Latest Update)

### Enhanced ByteTrack with Kalman Filtering
- **Smooth Trajectories**: Integrated Kalman filter for robust object tracking during occlusions
- **Configurable Noise Parameters**: Tune process and measurement noise for your specific camera setup
- **Improved ID Consistency**: Reduced track switching during worker-bag interactions

### Async Clip Processing
- **Non-blocking Recording**: Video clips saved using `ThreadPoolExecutor` to prevent frame drops
- **Background I/O**: Main detection pipeline runs at full FPS while clips are written to disk

### Robust Camera Error Handling
- **Auto-Reconnect**: Automatic reconnection on stream loss with configurable retry count
- **Health Monitoring**: Continuous camera status checks with graceful degradation
- **Recovery Logging**: Detailed logs of disconnection events and recovery attempts

### Structured Logging
- **Rotating File Handlers**: 10MB max file size, 7 days retention
- **Colored Console Output**: Easy-to-read logs during development
- **Log Levels**: Configurable verbosity (DEBUG, INFO, WARNING, ERROR)

### API Security
- **JWT Authentication**: Secure token-based access to API endpoints
- **Rate Limiting**: Prevent abuse with configurable request limits per IP
- **Admin Access Control**: Role-based permissions for sensitive operations

### Notification System
- **Multi-channel Alerts**: SMTP email and Telegram bot notifications
- **Event-driven Triggers**: Notifications on wagon closure, low stock, system errors
- **Configurable Recipients**: Different notification channels for different event types

---

## Architecture

See `docs/architecture.mmd` for the Mermaid data-flow diagram.

## Directory Structure

```
bag_counter_edge/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── docs/
│   └── architecture.mmd
├── src/
│   ├── __init__.py
│   ├── main.py                     # Pipeline orchestrator
│   ├── config.py                   # Pydantic settings
│   ├── api/
│   │   ├── __init__.py
│   │   └── app.py                  # FastAPI (health, stats, auth)
│   ├── capture/
│   │   ├── __init__.py
│   │   └── camera_stream.py        # RTSP capture (threaded, auto-reconnect)
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── detector.py             # YOLOv8 bag detector
│   │   ├── tracker.py              # ByteTrack + Kalman filter
│   │   ├── volume_estimator.py     # Depth / pixel volume proxy
│   │   ├── tripwire.py             # Virtual tripwire logic
│   │   └── handover_logic.py       # Worker handover validation
│   ├── db/
│   │   ├── __init__.py
│   │   └── models.py               # SQLAlchemy ORM
│   ├── nvr/
│   │   ├── __init__.py
│   │   └── clip_recorder.py        # Async FFmpeg clip cutter
│   ├── notifications/
│   │   ├── __init__.py
│   │   ├── notifier.py             # Multi-channel notification service
│   │   └── templates.py            # Notification message templates
│   ├── training/
│   │   ├── __init__.py
│   │   ├── finetune_yolo.py        # YOLOv8 fine-tuning script
│   │   └── dataset_utils.py        # LabelMe -> YOLO converter
│   └── kiosk/
│       ├── __init__.py
│       └── dashboard.py            # Streamlit operator UI
├── models/                         # YOLO weights (mounted RO)
├── logs/                           # Rotating log files
└── storage/
    ├── clips/                      # 5-second event clips
    ├── db/                         # SQLite
    └── nvr/                        # Continuous 10-min segments
```

## Configuration

### Environment Variables

Create a `.env` file in the project root or set environment variables directly:

```bash
# Camera Streams
PRIMARY_STREAM_URL=rtsp://admin:password@192.168.1.100:554/stream1
