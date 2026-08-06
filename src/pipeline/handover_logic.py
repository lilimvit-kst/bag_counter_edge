"""
Handover logic: determines when a bag has been physically removed by a worker.
Prevents double-counting and handles occlusion.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.config import settings
from src.pipeline.tracker import Track


class HandoverLogic:
    """
    A bag is considered "handed over" (counted) when ALL of the following hold:
      1. It has crossed the tripwire.
      2. It disappears from the ROI for >= HANDOVER_DISAPPEAR_FRAMES.
      3. It was never re-detected inside ROI with the same track ID after crossing.
    """

    def __init__(self) -> None:
        self.disappear_threshold = settings.HANDOVER_DISAPPEAR_FRAMES
        self.roi = (
            settings.ROI_X1_RATIO,
            settings.ROI_Y1_RATIO,
            settings.ROI_X2_RATIO,
            settings.ROI_Y2_RATIO,
        )

    def is_inside_roi(self, bbox: np.ndarray, frame_w: int, frame_h: int) -> bool:
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0
        x1r, y1r, x2r, y2r = self.roi
        return (
            x1r * frame_w <= cx <= x2r * frame_w
            and y1r * frame_h <= cy <= y2r * frame_h
        )

    def evaluate(
        self,
        track: Track,
        frame_w: int,
        frame_h: int,
    ) -> bool:
        if not track.crossed_tripwire:
            return False
        if track.counted:
            return False

        inside = self.is_inside_roi(track.bbox, frame_w, frame_h)
        if inside:
            # Reset disappear counter if re-appears inside ROI
            track.disappeared = 0
            return False

        if track.disappeared >= self.disappear_threshold:
            return True
        return False
