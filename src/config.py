"""
Project-wide configuration and constants.
"""
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Paths
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    STORAGE_DIR: Path = PROJECT_ROOT / "storage"
    CLIPS_DIR: Path = STORAGE_DIR / "clips"
    DB_PATH: Path = STORAGE_DIR / "db" / "bag_counter.db"
    MODELS_DIR: Path = PROJECT_ROOT / "models"
    LOGS_DIR: Path = STORAGE_DIR / "logs"

    # Camera / Stream
    PRIMARY_STREAM_URL: str = "rtsp://192.168.1.100:554/stream1"  # RGB
    SECONDARY_STREAM_URL: str = "rtsp://192.168.1.101:554/stream1"  # Optional depth / stereo
    FRAME_WIDTH: int = 1920
    FRAME_HEIGHT: int = 1080
    FPS: int = 25
    CAMERA_RECONNECT_DELAY: float = 2.0
    CAMERA_MAX_RECONNECT_ATTEMPTS: int = 5

    # Detection
    DETECTION_MODEL: str = "yolov8n.pt"  # Fine-tuned on bags
    CONFIDENCE_THRESHOLD: float = 0.65
    IOU_THRESHOLD: float = 0.45
    BAG_CLASS_IDS: list[int] = [0]  # Single class "flour_bag"

    # Volume / Classification
    EMPTY_VOLUME_MAX: float = 3.0   # liters, below -> empty
    VOLUME_25KG_MAX: float = 35.0   # liters, 25 kg bag range
    # Anything between EMPTY_VOLUME_MAX and VOLUME_25KG_MAX -> 25 kg
    # Above VOLUME_25KG_MAX -> 50 kg

    # Tracking
    TRACK_MAX_AGE: int = 30         # frames
    TRACK_MIN_HITS: int = 3
    TRACK_IOU_THRESHOLD: float = 0.3
    KALMAN_PROCESS_NOISE: float = 1e-4
    KALMAN_MEASUREMENT_NOISE: float = 1e-2

    # Tripwire / Handover
    TRIPWIRE_Y_RATIO: float = 0.75  # Horizontal line at 75% of frame height
    HANDOVER_DISAPPEAR_FRAMES: int = 10  # frames missing before "handed over"
    ROI_X1_RATIO: float = 0.1
    ROI_X2_RATIO: float = 0.9
    ROI_Y1_RATIO: float = 0.2
    ROI_Y2_RATIO: float = 0.9

    # NVR / Clips
    CLIP_PREROLL_SEC: float = 2.0
    CLIP_POSTROLL_SEC: float = 3.0
    NVR_RETENTION_DAYS: int = 7
    NVR_SEGMENT_MINUTES: int = 10
    CLIP_POOL_SIZE: int = 4  # ThreadPoolExecutor workers for clip saving

    # Shift / Wagon defaults
    SHIFT_DURATION_HOURS: float = 12.0

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_ROTATION_SIZE: str = "10 MB"
    LOG_RETENTION_DAYS: int = 7
    LOG_FILE_PATH: Path = LOGS_DIR / "bag_counter.log"

    # API Security
    API_SECRET_KEY: str = Field(default="change-me-in-production", env="API_SECRET_KEY")
    API_TOKEN_EXPIRE_MINUTES: int = 30
    API_RATE_LIMIT_PER_MINUTE: int = 60
    API_ADMIN_USER: str = Field(default="admin", env="API_ADMIN_USER")
    API_ADMIN_PASS: str = Field(default="admin", env="API_ADMIN_PASS")

    # Notifications
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    EMAIL_FROM: str = ""
    EMAIL_TO: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    NOTIFY_ON_WAGON_CLOSE: bool = True
    NOTIFY_ON_LOW_STOCK: bool = False
    LOW_STOCK_THRESHOLD: int = 100

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
