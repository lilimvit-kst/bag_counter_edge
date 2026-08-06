"""
Project-wide configuration and constants.
"""
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Paths
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    STORAGE_DIR: Path = PROJECT_ROOT / "storage"
    CLIPS_DIR: Path = STORAGE_DIR / "clips"
    DB_PATH: Path = STORAGE_DIR / "db" / "bag_counter.db"
    MODELS_DIR: Path = PROJECT_ROOT / "models"

    # Camera / Stream
    PRIMARY_STREAM_URL: str = "rtsp://192.168.1.100:554/stream1"  # RGB
    SECONDARY_STREAM_URL: str = "rtsp://192.168.1.101:554/stream1"  # Optional depth / stereo
    FRAME_WIDTH: int = 1920
    FRAME_HEIGHT: int = 1080
    FPS: int = 25

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

    # Shift / Wagon defaults
    SHIFT_DURATION_HOURS: float = 12.0

    class Config:
        env_file = ".env"


settings = Settings()
