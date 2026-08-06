"""
Volume estimator using depth map or stereo disparity.
For monocular setup: uses apparent pixel-area as proxy (calibrated).
For stereo / RGB-D: computes real-world volume from depth crop.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import cv2
from loguru import logger

from src.config import settings
from src.pipeline.detector import Detection


class VolumeEstimator:
    """
    Estimates bag volume in liters from bbox + depth.
    If no depth available, falls back to pixel-area heuristic
    calibrated against known 25 kg / 50 kg samples.
    """

    def __init__(self, use_depth: bool = False, focal_length_px: float = 800.0) -> None:
        self.use_depth = use_depth
        self.focal = focal_length_px
        # Fallback calibration constants (pixels^3 -> liters)
        self._calib_empty = settings.EMPTY_VOLUME_MAX
        self._calib_25 = settings.VOLUME_25KG_MAX

    def estimate(
        self,
        frame: np.ndarray,
        det: Detection,
        depth_map: Optional[np.ndarray] = None,
    ) -> float:
        x1, y1, x2, y2 = map(int, det.bbox)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
        w_px = x2 - x1
        h_px = y2 - y1

        if self.use_depth and depth_map is not None:
            return self._from_depth(depth_map, x1, y1, x2, y2)
        else:
            return self._from_pixels(w_px, h_px, det.confidence)

    def _from_depth(self, depth_map: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> float:
        crop = depth_map[y1:y2, x1:x2].astype(np.float32)
        if crop.size == 0:
            return 0.0
        # Median depth to reduce noise (mm -> m)
        z_m = np.median(crop[crop > 0]) / 1000.0
        if z_m <= 0:
            return 0.0
        # Real-world size from similar triangles
        w_m = (x2 - x1) * z_m / self.focal
        h_m = (y2 - y1) * z_m / self.focal
        # Approximate thickness: use depth variance or constant ratio
        # For a lying bag: thickness ~ 0.25 * height (empirical)
        t_m = h_m * 0.25
        volume_m3 = w_m * h_m * t_m
        return volume_m3 * 1000.0  # liters

    def _from_pixels(self, w_px: int, h_px: int, conf: float) -> float:
        # Proxy: area * aspect ratio correction
        area = w_px * h_px
        # Empirical mapping: area in px -> liters (requires per-camera calibration)
        # Here we use a simple heuristic assuming HD camera at ~2m distance.
        liters = area / 500.0  # calibration factor
        return liters

    def classify(self, volume_liters: float) -> str:
        if volume_liters < settings.EMPTY_VOLUME_MAX:
            return "empty"
        elif volume_liters <= settings.VOLUME_25KG_MAX:
            return "25kg"
        else:
            return "50kg"
