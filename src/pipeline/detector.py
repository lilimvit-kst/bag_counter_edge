"""
Bag detector based on Ultralytics YOLO.
Expects a fine-tuned model where class 0 = flour_bag.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from ultralytics import YOLO
from loguru import logger

from src.config import settings


@dataclass(frozen=True)
class Detection:
    bbox: np.ndarray  # [x1, y1, x2, y2] in pixels
    confidence: float
    class_id: int


class BagDetector:
    def __init__(self, model_path: Optional[str] = None) -> None:
        path = model_path or str(settings.MODELS_DIR / settings.DETECTION_MODEL)
        logger.info(f"Loading YOLO model from {path}")
        self.model = YOLO(path)
        self.conf = settings.CONFIDENCE_THRESHOLD
        self.iou = settings.IOU_THRESHOLD

    def predict(self, frame: np.ndarray) -> List[Detection]:
        """
        Run inference on a single BGR frame.
        Returns list of detections filtered to bag class only.
        """
        results = self.model.predict(
            source=frame,
            conf=self.conf,
            iou=self.iou,
            verbose=False,
            device="cpu",  # Change to "0" if CUDA available on Edge
        )
        detections: List[Detection] = []
        if not results:
            return detections

        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls.item())
                if cls_id not in settings.BAG_CLASS_IDS:
                    continue
                xyxy = box.xyxy.cpu().numpy().flatten()
                conf = float(box.conf.item())
                detections.append(Detection(bbox=xyxy, confidence=conf, class_id=cls_id))
        return detections
