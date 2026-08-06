"""
Simple IOU-based tracker with Kalman filtering (conceptual ByteTrack lite).
Production-grade: swap to ultralytics.track() or real ByteTrack implementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

from src.config import settings
from src.pipeline.detector import Detection


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    """Compute IoU between two boxes [x1,y1,x2,y2]."""
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _box_center(b: np.ndarray) -> Tuple[float, float]:
    return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)


@dataclass
class Track:
    id: int
    bbox: np.ndarray
    age: int = 0
    hits: int = 1
    last_seen: int = 0
    disappeared: int = 0
    crossed_tripwire: bool = False
    counted: bool = False
    volume_liters: float = 0.0
    bag_class: Optional[str] = None
    history: List[np.ndarray] = field(default_factory=list)


class BagTracker:
    """
    Lightweight tracker for conveyor-bag scenarios.
    Assumes mostly linear motion along one axis.
    """

    def __init__(self) -> None:
        self.next_id = 1
        self.tracks: Dict[int, Track] = {}
        self.frame_count = 0
        self.max_age = settings.TRACK_MAX_AGE
        self.min_hits = settings.TRACK_MIN_HITS
        self.iou_threshold = settings.TRACK_IOU_THRESHOLD

    def update(self, detections: List[Detection]) -> List[Track]:
        self.frame_count += 1
        assigned: set[int] = set()

        # 1. Predict / age existing tracks
        for t in self.tracks.values():
            t.age += 1
            t.disappeared += 1

        # 2. Hungarian-ish greedy matching by IoU
        det_indices = list(range(len(detections)))
        track_items = list(self.tracks.items())
        # Build cost matrix (negative IoU)
        if track_items and detections:
            cost = np.zeros((len(track_items), len(detections)))
            for ti, (_, tr) in enumerate(track_items):
                for di, det in enumerate(detections):
                    cost[ti, di] = _iou(tr.bbox, det.bbox)
            # Greedy match
            matched_tracks: Dict[int, int] = {}
            while cost.max() > self.iou_threshold:
                ti, di = np.unravel_index(np.argmax(cost), cost.shape)
                matched_tracks[track_items[ti][0]] = di
                assigned.add(di)
                cost[ti, :] = -1.0
                cost[:, di] = -1.0

            # Update matched
            for tid, di in matched_tracks.items():
                det = detections[di]
                t = self.tracks[tid]
                # Simple alpha blend for smoothing
                alpha = 0.7
                t.bbox = alpha * det.bbox + (1 - alpha) * t.bbox
                t.hits += 1
                t.disappeared = 0
                t.age = 0
                t.history.append(t.bbox.copy())
                if len(t.history) > 30:
                    t.history.pop(0)

        # 3. Create new tracks for unmatched detections
        for di, det in enumerate(detections):
            if di in assigned:
                continue
            t = Track(
                id=self.next_id,
                bbox=det.bbox.copy(),
                last_seen=self.frame_count,
            )
            self.tracks[self.next_id] = t
            self.next_id += 1

        # 4. Delete stale tracks
        stale = [tid for tid, t in self.tracks.items() if t.disappeared > self.max_age]
        for tid in stale:
            del self.tracks[tid]

        # Return active confirmed tracks
        active = [t for t in self.tracks.values() if t.hits >= self.min_hits]
        return active
