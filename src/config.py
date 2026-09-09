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

    # Camera / Stream - mapped directly from .env variables (Pydantic auto-maps by name)
    CAMERA_SOURCE: str = Field(default="rtsp://192.168.1.100:554/stream1")
    SECONDARY_STREAM_URL: str = Field(default="")
    CAMERA_WIDTH: int = Field(default=1920)
    CAMERA_HEIGHT: int = Field(default=1080)
    CAMERA_FPS: int = Field(default=25)
    CAMERA_RECONNECT_DELAY: float = 2.0
    CAMERA_MAX_RECONNECT_ATTEMPTS: int = 5
    
    # Alias for backward compatibility with code using PRIMARY_STREAM_URL, FRAME_WIDTH, etc.
    @property
    def PRIMARY_STREAM_URL(self) -> str:
        return self.CAMERA_SOURCE
    
    @property
    def FRAME_WIDTH(self) -> int:
        return self.CAMERA_WIDTH
    
    @property
    def FRAME_HEIGHT(self) -> int:
        return self.CAMERA_HEIGHT
    
    @property
    def FPS(self) -> int:
        return self.CAMERA_FPS

    # Detection
    DETECTION_MODEL: str = Field(default="yolov8n.pt", env="YOLO_MODEL_PATH")
    CONFIDENCE_THRESHOLD: float = Field(default=0.65, env="CONFIDENCE_THRESHOLD")
    IOU_THRESHOLD: float = Field(default=0.45, env="IOU_THRESHOLD")
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
    TRIPWIRE_Y_RATIO: float = Field(default=0.75, env="TRIPWIRE_Y_RATIO")
    HANDOVER_DISAPPEAR_FRAMES: int = Field(default=10, env="HANDOVER_DISAPPEAR_FRAMES")
    ROI_X1_RATIO: float = Field(default=0.1, env="ROI_X1_RATIO")
    ROI_X2_RATIO: float = Field(default=0.9, env="ROI_X2_RATIO")
    ROI_Y1_RATIO: float = Field(default=0.2, env="ROI_Y1_RATIO")
    ROI_Y2_RATIO: float = Field(default=0.9, env="ROI_Y2_RATIO")

    # NVR / Clips
    CLIP_PREROLL_SEC: float = Field(default=2.0, env="NVR_PRE_EVENT_DURATION")
    CLIP_POSTROLL_SEC: float = Field(default=3.0, env="NVR_POST_EVENT_DURATION")
    NVR_RETENTION_DAYS: int = Field(default=7, env="NVR_RETENTION_DAYS")
    NVR_SEGMENT_MINUTES: int = Field(default=10, env="NVR_SEGMENT_MINUTES")
    CLIP_POOL_SIZE: int = 4  # ThreadPoolExecutor workers for clip saving

    # Shift / Wagon defaults
    SHIFT_DURATION_HOURS: float = 12.0

    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_ROTATION_SIZE: str = "10 MB"
    LOG_RETENTION_DAYS: int = 7
    LOG_FILE_PATH: Path = LOGS_DIR / "bag_counter.log"

    # API Security
    API_SECRET_KEY: str = Field(default="change-me-in-production", env="API_SECRET_KEY")
    API_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    API_RATE_LIMIT_PER_MINUTE: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    API_ADMIN_USER: str = Field(default="admin", env="ADMIN_USERNAME")
    API_ADMIN_PASS: str = Field(default="admin", env="ADMIN_PASSWORD")

    # Notifications
    SMTP_HOST: str = Field(default="", env="SMTP_SERVER")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USER: str = Field(default="", env="SMTP_USER")
    SMTP_PASS: str = Field(default="", env="SMTP_PASSWORD")
    EMAIL_FROM: str = Field(default="", env="NOTIFICATION_EMAIL")
    EMAIL_TO: str = Field(default="", env="NOTIFICATION_EMAIL")
    TELEGRAM_BOT_TOKEN: str = Field(default="", env="TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID: str = Field(default="", env="TELEGRAM_CHAT_ID")
    NOTIFY_ON_WAGON_CLOSE: bool = Field(default=True, env="ENABLE_EMAIL_NOTIFICATIONS")
    NOTIFY_ON_LOW_STOCK: bool = False
    LOW_STOCK_THRESHOLD: int = 100
    
    # Redis / Celery
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0", env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0", env="CELERY_RESULT_BACKEND")
    CELERY_ENABLED: bool = Field(default=False, env="CELERY_ENABLED")
    WEBSOCKET_ENABLED: bool = Field(default=True, env="WEBSOCKET_ENABLED")
    WEBSOCKET_PORT: int = 8765

    DASHBOARD_SOURCE_ID: str = "primary"
    DASHBOARD_TELEMETRY_TTL: int = Field(default=5, ge=2)
    DASHBOARD_CAMERA_TIMEOUT: float = Field(default=5.0, gt=0)
    DASHBOARD_PROCESSING_TIMEOUT: float = Field(default=15.0, gt=0)
    
    # Dashboard / API configuration (for kiosk service)
    API_HOST: str = Field(default="localhost", env="API_HOST")
    API_PORT: int = Field(default=8000, env="API_PORT")
    INTERNAL_API_HOST: str = Field(default="edge-cv", env="INTERNAL_API_HOST")
    # GUI settings (disable in Docker/headless environments)
    USE_GUI: bool = Field(default=True, env="USE_GUI")
    
    @property
    def API_BASE_URL(self) -> str:
        """Get base URL for API calls from dashboard."""
        return f"http://{self.API_HOST}:{self.API_PORT}"
    
    @property
    def INTERNAL_API_BASE_URL(self) -> str:
        """Get internal API URL for Docker network communication."""
        return f"http://{self.INTERNAL_API_HOST}:{self.API_PORT}"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
