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
SECONDARY_STREAM_URL=rtsp://admin:password@192.168.1.101:554/stream1

# YOLO Model
MODEL_PATH=models/best_bag.pt
CONFIDENCE_THRESHOLD=0.45
IOU_THRESHOLD=0.7

# Tracker Settings (ByteTrack + Kalman)
TRACK_MAX_AGE=30
TRACK_MIN_HITS=3
KALMAN_PROCESS_NOISE=0.05
KALMAN_MEASUREMENT_NOISE=0.01

# Camera Reconnect
CAMERA_RECONNECT_DELAY=5
CAMERA_MAX_RETRIES=10

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/bag_counter.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=7

# API Security
API_SECRET_KEY=your-super-secret-key-change-in-production
API_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Notifications - SMTP
SMTP_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com
SMTP_TO_EMAILS=manager@example.com,supervisor@example.com

# Notifications - Telegram
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=-1001234567890

# Notification Triggers
NOTIFY_ON_WAGON_CLOSE=true
NOTIFY_ON_LOW_STOCK=true
NOTIFY_ON_CAMERA_ERROR=true
NOTIFY_ON_SYSTEM_ERROR=true
```

### Configuration Classes

All settings are managed via Pydantic settings classes in `src/config.py`:

- `Settings`: Main configuration class
- `TrackerSettings`: ByteTrack + Kalman filter parameters
- `CameraSettings`: Stream URLs and reconnect logic
- `LogSettings`: Logging configuration
- `SecuritySettings`: JWT and rate limiting
- `NotificationSettings`: SMTP and Telegram settings

---

## Fine-Tuning YOLOv8 on Your Bags

### 1. Prepare Dataset

Annotate images using **LabelMe** or **CVAT**, then convert to YOLO format:

```bash
python -m src.training.dataset_utils \
    --labelme-dir data/labelme_annotations/ \
    --output-dir data/labels/ \
    --class-map '{"empty_bag":0,"bag_25kg":1,"bag_50kg":2}'
```

Or use the helper programmatically:

```python
from pathlib import Path
from src.training.dataset_utils import convert_labelme_to_yolo, split_dataset, generate_data_yaml

# 1. Convert annotations
convert_labelme_to_yolo(Path("annotations/"), Path("labels/"))

# 2. Split into train/val
split_dataset(Path("images/"), Path("labels/"), Path("data/"), train_ratio=0.8)

# 3. Generate data.yaml
generate_data_yaml(
    Path("data/data.yaml"),
    Path("data"),
    ["empty_bag", "bag_25kg", "bag_50kg"]
)
```

### 2. Train

```bash
python -m src.training.finetune_yolo \
    --data data/data.yaml \
    --model yolov8n.pt \
    --epochs 100 \
    --imgsz 640 \
    --batch 8 \
    --device cpu \
    --project runs/bag_training \
    --name bag_yolo_v1 \
    --export
```

**Key flags:**
- `--model yolov8n.pt` — start from nano (fastest on Edge). Use `s`, `m`, `l` for better accuracy.
- `--device 0` — use GPU if available.
- `--export` — export trained model to ONNX for inference optimization.
- `--copy-best models/best_bag.pt` — automatically copy best weights to project `models/`.

### 3. Augmentations Applied

The training script applies augmentations tuned for industrial conveyor scenarios:
- **Mosaic**: `1.0` (helps with occlusion and overlapping bags)
- **Mixup**: `0.1`
- **HSV**: hue ±1.5%, saturation ±70%, value ±40% (lighting invariant)
- **Scale**: ±50%, **Shear**: ±2°, **Translation**: ±10%
- **RandAugment**: auto policy

---

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Get JWT access token |
| POST | `/api/v1/auth/refresh` | Refresh access token |

**Example Login:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}'
```

### Protected Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v1/health` | System health check | No |
| GET | `/api/v1/stats` | Current counting stats | Yes |
| GET | `/api/v1/events` | Recent events log | Yes |
| POST | `/api/v1/wagon/close` | Close current wagon | Yes (Admin) |
| POST | `/api/v1/wagon/new` | Start new wagon | Yes (Admin) |
| POST | `/api/v1/shift/end` | End current shift | Yes (Admin) |
| GET | `/api/v1/cameras/status` | Camera health status | Yes |
| GET | `/api/v1/clips/{event_id}` | Download event clip | Yes |

**Rate Limiting:** All authenticated endpoints are limited to 100 requests per minute per IP.

---

## Notification System

### Supported Channels

1. **SMTP Email**: Send emails on critical events
2. **Telegram Bot**: Instant messages to Telegram groups/channels

### Event Types

| Event | Trigger | Channels |
|-------|---------|----------|
| `wagon_closed` | Wagon counting completed | Email, Telegram |
| `low_stock` | Bag count below threshold | Email, Telegram |
| `camera_error` | Camera stream lost | Telegram |
| `system_error` | Critical system failure | Email, Telegram |
| `reconnect_success` | Camera reconnected | Telegram (optional) |

### Example Notification Payload

```json
{
  "event_type": "wagon_closed",
  "timestamp": "2025-01-15T14:30:00Z",
  "data": {
    "wagon_id": "W-2025-0042",
    "total_bags": 1250,
    "bags_25kg": 800,
    "bags_50kg": 450,
    "estimated_weight_tons": 38.5,
    "shift_id": "S-2025-01-15-A"
  }
}
```

### Testing Notifications

```bash
# Test email notification
curl -X POST http://localhost:8000/api/v1/notifications/test/email \
  -H "Authorization: Bearer YOUR_TOKEN"

# Test Telegram notification
curl -X POST http://localhost:8000/api/v1/notifications/test/telegram \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Operator Dashboard (Streamlit)

A local web UI for the shift supervisor to monitor counts and control wagons.

### Features
- **Live stats**: total bags, estimated weight, active shift/wagon
- **Class breakdown**: 25 kg / 50 kg / empty counters
- **Event log**: last 30 counted bags with timestamps and clip links
- **Notification status**: View enabled notification channels
- **Alert history**: Past notifications with delivery status
- **Actions**:
  - 🚪 **Close Wagon** — finalize current wagon, save totals
  - 🔄 **Start New Wagon** — begin counting next wagon
  - 🌙 **End Shift** — close shift and start new one
  - 🔔 **Test Notifications** — send test alerts

### Run Dashboard

```bash
streamlit run src/kiosk/dashboard.py
```

Open browser at `http://localhost:8501`.

### Docker Compose (with Dashboard)

The `docker-compose.yml` includes a dashboard service. Access at `http://<edge-pc-ip>:8501`.

---

## Edge-Cases & Mitigations

### 1. Worker occludes bag during handover
**Problem:** The worker's body blocks the camera view; the tracker loses the bag or spawns a new ID after occlusion.
**Mitigation:**
- Increase `TRACK_MAX_AGE` (e.g. 30 frames ≅ 1.2 s at 25 FPS) so the track stays alive during brief occlusion.
- Kalman filter predicts position during occlusion, maintaining track continuity.
- Use ROI + disappearance logic: do **not** count until the bag has been missing from the ROI for `HANDOVER_DISAPPEAR_FRAMES` *after* crossing the tripwire. This prevents counting while the bag is merely hidden behind the worker but still in the ROI.
- Optional: add a second camera at a different angle (stereo or side-view) to maintain visibility.

### 2. Double-counting when a bag is shifted but not removed
**Problem:** The worker pushes a bag to the side of the conveyor (it crosses the tripwire) but does not take it into the wagon; later the bag re-enters the ROI.
**Mitigation:**
- Handover logic requires **both** tripwire crossing **and** disappearance from ROI for >= N frames.
- If the bag re-appears inside ROI with the same track ID, `disappeared` counter resets to 0 and `counted` flag remains false.
- Persist track ID in a short-term "ghost" cache (e.g. 5 s) after deletion; if a new detection matches the ghost bbox/position, inherit the old ID and keep `counted=False` if it was not previously counted.

### 3. Empty / flat bags counted as valid 25 kg
**Problem:** A deflated or empty bag rides the conveyor with low volume but is detected as a valid bag.
**Mitigation:**
- Volume estimator classifies bags below `EMPTY_VOLUME_MAX` liters as `BagClass.EMPTY`.
- The pipeline ignores empty bags: they are tracked but `_count_bag()` is never called for `bag_class == "empty"`.
- Add a second validation stage: compare bag aspect ratio. Empty bags often have very high aspect ratio (long and flat). Reject detections where `width / height > 4.0` after tripwire crossing.

---

## Troubleshooting

### Camera Connection Issues

1. **Check stream URL**: Verify RTSP URL with VLC player
2. **Network connectivity**: Ping camera IP address
3. **Credentials**: Confirm username/password in `.env`
4. **Logs**: Check `logs/bag_counter.log` for detailed error messages

```bash
# Test RTSP stream with FFmpeg
ffmpeg -i rtsp://admin:password@192.168.1.100:554/stream1 -f null -
```

### Notification Delivery Failures

1. **SMTP**: Verify app-specific password (Gmail requires app password)
2. **Telegram**: Ensure bot token is valid and chat ID is correct
3. **Firewall**: Check outbound connections on ports 587 (SMTP) and 443 (Telegram)

```bash
# Test SMTP connection
telnet smtp.gmail.com 587

# Test Telegram bot
curl https://api.telegram.org/botYOUR_TOKEN/getMe
```

### Tracking Quality Issues

If bags are losing track IDs frequently:

1. Increase `TRACK_MAX_AGE` (default: 30 frames)
2. Adjust Kalman noise parameters:
   - Higher `KALMAN_PROCESS_NOISE` for erratic motion
   - Lower `KALMAN_MEASUREMENT_NOISE` for stable cameras
3. Ensure adequate lighting and minimal motion blur

---

## Quick Start

```bash
# 1. Place your fine-tuned YOLO weights into models/
cp your_bag_yolo.pt models/

# 2. Configure environment
cp .env.example .env
# Edit PRIMARY_STREAM_URL, etc.

# 3. Run with Docker Compose
docker compose up --build

# 4. Or run locally
pip install -r requirements.txt
python -m src.main
```

---

## Development

### Running Tests

```bash
pytest tests/ -v --cov=src
```

### Code Quality

```bash
# Linting
flake8 src/
pylint src/

# Type checking
mypy src/

# Formatting
black src/
isort src/
```

### Building Docker Image

```bash
docker build -t bag-counter-edge:latest .
```

### Docker Compose

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Restart specific service
docker compose restart tracker
```

---

## License

Proprietary — All rights reserved.

## Contact

For support, contact: support@example.com

---

## Docker & Контейнеризация

Проект полностью контейнеризирован с использованием Docker и Docker Compose для обеспечения согласованности сред и упрощения развертывания.

### Архитектура контейнеров

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│      Web        │────▶│     Redis        │◀────│    Celery       │
│   (FastAPI)     │     │   (Broker/Cache) │     │    Worker       │
│   Port: 8000    │     │   Port: 6379     │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         ▲                       ▲                        ▲
         │                       │                        │
         │                ┌──────────────┐                │
         └────────────────│   Flower     │◀───────────────┘
                          │ (Monitoring) │
                          │ Port: 5555   │
                          └──────────────┘
                                 ▲
                                 │
                          ┌──────────────┐
                          │ Celery Beat  │
                          │ (Scheduler)  │
                          └──────────────┘
```

### Сервисы

| Сервис | Описание | Порт | Образ |
|--------|----------|------|-------|
| `web` | FastAPI приложение (API + WebSocket) | 8000 | `bag-counter-edge:latest` |
| `worker` | Celery worker для фоновых задач | - | `bag-counter-edge:worker` |
| `beat` | Celery beat для периодических задач | - | `bag-counter-edge:worker` |
| `redis` | Брокер сообщений и кэш | 6379 | `redis:7-alpine` |
| `flower` | Мониторинг Celery задач | 5555 | `mher/flower:latest` |

### Сборка образов

```bash
# Сборка основного образа
docker build -t bag-counter-edge:latest .

# Сборка образа для workers
docker build -f Dockerfile.worker -t bag-counter-edge:worker .

# Или через docker-compose (автоматически)
docker-compose build
```

### Запуск стека

```bash
# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f worker

# Остановка всех сервисов
docker-compose down

# Остановка с удалением томов (данные будут потеряны)
docker-compose down -v
```

### Переменные окружения для Docker

Все переменные из `.env` автоматически передаются в контейнеры. Дополнительные параметры:

```bash
# Docker-specific
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Масштабирование workers
# Запустить 3 worker контейнера
docker-compose up -d --scale worker=3
```

### Мониторинг с Flower

Flower предоставляет веб-интерфейс для мониторинга Celery задач:

```bash
# Доступ к Flower
open http://localhost:5555

# Или в браузере: http://localhost:5555
```

**Возможности Flower:**
- Просмотр активных, запланированных и завершенных задач
- Статистика по workers (загрузка, память)
- Графики выполнения задач
- Управление задачами (отмена, повтор)

### Примеры команд

```bash
# Выполнить миграции БД внутри контейнера
docker-compose exec web python -m src.db.migrate

# Запустить тесты
docker-compose exec web pytest tests/ -v

# Открыть shell в контейнере
docker-compose exec web bash

# Посмотреть статус Redis
docker-compose exec redis redis-cli ping

# Экспорт логов в файл
docker-compose logs > logs/full.log 2>&1
```

### Оптимизация образов

Образы оптимизированы для минимального размера:
- **Основной образ**: ~450MB (многоступенчатая сборка, slim base)
- **Worker образ**: ~420MB (без экспорта портов)
- **Очистка кэша**: Удаление apt cache, pip cache после установки

### Production рекомендации

1. **Безопасность**:
   - Замените секретные ключи в `.env`
   - Используйте Docker secrets для чувствительных данных
   - Не запускайте от root (добавьте USER в Dockerfile)

2. **Ресурсы**:
   ```yaml
   # Ограничение ресурсов в docker-compose.yml
   deploy:
     resources:
       limits:
         cpus: '2'
         memory: 2G
       reservations:
         cpus: '1'
         memory: 1G
   ```

3. **Логирование**:
   ```yaml
   # Настройка логирования
   logging:
     driver: "json-file"
     options:
       max-size: "10m"
       max-file: "3"
   ```

4. **Health checks**:
   - Все сервисы имеют health checks
   - Автоматический перезапуск при сбоях (`restart: unless-stopped`)

---

## Очередь задач (Celery + Redis)

Система использует Celery с Redis в качестве брокера для асинхронной обработки тяжелых задач.

### Типы задач

| Задача | Описание | Периодичность |
|--------|----------|---------------|
| `process_event_clip` | Обработка и сохранение видео клипа | По событию |
| `send_notification` | Отправка уведомления (email/Telegram) | По событию |
| `generate_daily_report` | Генерация ежедневного отчета | Ежедневно в 23:00 |
| `update_dashboard_stats` | Обновление статистики dashboard | Каждые 30 сек |
| `cleanup_old_clips` | Очистка старых клипов | Ежедневно в 03:00 |

### Запуск Workers

```bash
# Один worker
docker-compose up -d worker

# Несколько workers (масштабирование)
docker-compose up -d --scale worker=3

# Логи workers
docker-compose logs -f worker

# Мониторинг через Flower
open http://localhost:5555
```

### Примеры задач

**Отправка уведомления:**
```python
from src.tasks.notifications import send_notification_task

# Асинхронная отправка
send_notification_task.delay(
    event_type="wagon_closed",
    data={"wagon_id": "W-001", "total_bags": 1250}
)
```

**Обработка клипа:**
```python
from src.tasks.clips import process_event_clip_task

process_event_clip_task.delay(
    event_id="evt_123",
    clip_path="/storage/clips/evt_123.mp4"
)
```

### Периодические задачи (Celery Beat)

Настроены в `src/tasks/config.py`:

```python
beat_schedule = {
    'cleanup-old-clips': {
        'task': 'src.tasks.clips.cleanup_old_clips',
        'schedule': crontab(hour=3, minute=0),  # Каждый день в 03:00
    },
    'generate-daily-report': {
        'task': 'src.tasks.reports.generate_daily_report',
        'schedule': crontab(hour=23, minute=0),  # Каждый день в 23:00
    },
    'update-dashboard-stats': {
        'task': 'src.tasks.dashboard.update_dashboard_stats',
        'schedule': 30.0,  # Каждые 30 секунд
    },
}
```

### Мониторинг задач

**Через Flower:**
- Активные задачи в реальном времени
- История выполненных задач
- Статистика по времени выполнения
- Графики нагрузки workers

**Через API:**
```bash
# Статус задачи
curl http://localhost:8000/api/v1/tasks/{task_id}

# Отменить задачу
curl -X POST http://localhost:8000/api/v1/tasks/{task_id}/revoke
```

### Повторные попытки (Retry Logic)

Задачи с автоматическими повторными попытками при сбоях:

```python
@app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification_task(self, event_type, data):
    try:
        # Логика отправки
        ...
    except Exception as exc:
        # Экспоненциальная задержка: 60s, 120s, 240s
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

---

## WebSocket (Real-time обновления)

Система поддерживает WebSocket соединения для real-time передачи событий на dashboard и другие клиенты.

### Каналы (Channels)

| Канал | Описание | Подписчики |
|-------|----------|------------|
| `general` | Общие системные события | Все клиенты |
| `dashboard` | Обновления статистики dashboard | Operator UI |
| `events` | События подсчета мешков | Dashboard, внешние системы |
| `alerts` | Критические уведомления | Admin panel |

### Подключение к WebSocket

**JavaScript (Browser):**
```javascript
// Подключение к каналу dashboard
const ws = new WebSocket('ws://localhost:8000/ws/dashboard');

ws.onopen = () => {
    console.log('Connected to WebSocket');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
    
    // Обновление UI
    if (data.type === 'bag_counted') {
        updateCounter(data.bag_class, data.count);
    }
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onclose = () => {
    console.log('Connection closed, reconnecting...');
    setTimeout(() => location.reload(), 3000);
};
```

**Python клиент:**
```python
import asyncio
import websockets
import json

async def listen_events():
    uri = "ws://localhost:8000/ws/events"
    async with websockets.connect(uri) as websocket:
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            print(f"Событие: {data['type']}")
            print(f"Данные: {data}")

asyncio.run(listen_events())
```

### Формат сообщений

Все сообщения отправляются в формате JSON:

```json
{
    "type": "bag_counted",
    "timestamp": "2025-01-15T14:30:00Z",
    "channel": "events",
    "data": {
        "bag_id": "bag_12345",
        "bag_class": "bag_25kg",
        "confidence": 0.94,
        "track_id": 42,
        "wagon_id": "W-2025-0042"
    }
}
```

### Типы событий

| Тип события | Канал | Описание |
|-------------|-------|----------|
| `bag_counted` | events | Мешок успешно подсчитан |
| `wagon_closed` | events, alerts | Вагон закрыт |
| `camera_disconnected` | alerts | Камера потеряна |
| `camera_reconnected` | alerts | Камера восстановлена |
| `low_stock_alert` | alerts | Низкий запас мешков |
| `stats_updated` | dashboard | Статистика обновлена |
| `system_health` | general | Статус системы |

### Интеграция с Dashboard

Streamlit dashboard автоматически подключается к WebSocket для real-time обновлений:

```python
# В src/kiosk/dashboard.py
import streamlit as st
import asyncio
import websockets

@st.experimental_fragment
def live_stats():
    if "ws_connected" not in st.session_state:
        st.session_state.ws_connected = False
    
    # Подключение к WebSocket
    if not st.session_state.ws_connected:
        # Логика подключения
        ...
    
    # Обработка входящих сообщений
    for message in st.session_state.ws_messages:
        if message["type"] == "stats_updated":
            st.metric("Всего мешков", message["data"]["total"])
```

### Масштабирование WebSocket

Для production с несколькими instances FastAPI:

1. **Redis Pub/Sub**: Использование Redis для синхронизации сообщений между instances
2. **Sticky Sessions**: Настройка load balancer для sticky sessions
3. **Message Queue**: Отправка событий в Redis, рассылка всем подключенным clients

```python
# Пример с Redis Pub/Sub
async def publish_message(channel: str, message: dict):
    redis = await aioredis.from_url("redis://redis:6379")
    await redis.publish(channel, json.dumps(message))
```

### Troubleshooting WebSocket

**Проблема**: Клиент не может подключиться
- Проверьте, что WebSocket endpoint доступен: `curl -i http://localhost:8000/ws/dashboard`
- Убедитесь, что firewall не блокирует порт 8000
- Проверьте логи: `docker-compose logs web | grep websocket`

**Проблема**: Частые разрывы соединения
- Увеличьте таймауты в настройках WebSocket
- Реализуйте механизм reconnection на клиенте
- Проверьте стабильность сети

**Проблема**: Сообщения не доходят
- Проверьте, что задача публикации в WebSocket вызывается
- Убедитесь, что канал подписки совпадает с каналом публикации
- Проверьте логи WebSocket manager

---
