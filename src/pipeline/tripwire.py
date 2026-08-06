"""
Tripwire: virtual line that a bag must cross before it can be counted.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

from src.pipeline.tracker import Track


@dataclass
class Tripwire:
    """
    Horizontal line defined by y_ratio (0..1 of frame height).
    Direction: must cross from top to bottom (conveyor -> worker).
    """
    y_ratio: float = 0.75

    def y_px(self, frame_height: int) -> int:
        return int(frame_height * self.y_ratio)

    def check_crossing(
        self,
        track: Track,
        frame_height: int,
    ) -> Tuple[bool, bool]:
        """
        Returns (just_crossed, currently_below).
        Uses track history to determine direction.
        """
        if len(track.history) < 2:
            return False, False

        y_line = self.y_px(frame_height)
        # Current center y
        curr_cy = (track.bbox[1] + track.bbox[3]) / 2.0
        # Previous center y
        prev_cy = (track.history[-2][1] + track.history[-2][3]) / 2.0

        currently_below = curr_cy > y_line
        was_above = prev_cy <= y_line
        just_crossed = was_above and currently_below and not track.crossed_tripwire
        return just_crossed, currently_below
