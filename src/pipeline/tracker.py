"""
Simple IOU-based tracker with Kalman filtering for trajectory smoothing.
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


class SimpleKalmanFilter:
    """
    1D Kalman filter for box center position smoothing.
    Assumes constant velocity motion along conveyor axis.
    State: [x, y, vx, vy]
    Measurement: [x, y]
    """

    def __init__(
        self,
        process_noise: float = settings.KALMAN_PROCESS_NOISE,
        measurement_noise: float = settings.KALMAN_MEASUREMENT_NOISE,
    ) -> None:
        # State transition matrix (constant velocity)
        self.F = np.array([
            [1, 0, 1, 0],
            [0, 1, 0, 1],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ], dtype=np.float32)

        # Measurement matrix
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
        ], dtype=np.float32)

        # Process noise covariance
        self.Q = np.eye(4, dtype=np.float32) * process_noise

        # Measurement noise covariance
        self.R = np.eye(2, dtype=np.float32) * measurement_noise

        # Error covariance
        self.P = np.eye(4, dtype=np.float32)

        # State vector
        self.x = np.zeros(4, dtype=np.float32)

        self.initialized = False

    def predict(self) -> Tuple[float, float]:
        """Predict next state and return predicted center."""
        if not self.initialized:
            return 0.0, 0.0

        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

        return float(self.x[0]), float(self.x[1])

    def update(self, measurement: Tuple[float, float]) -> Tuple[float, float]:
        """Update state with measurement and return smoothed center."""
        z = np.array(measurement, dtype=np.float32)

        if not self.initialized:
            # Initialize state with first measurement
            self.x[0] = z[0]  # x
            self.x[1] = z[1]  # y
            self.x[2] = 0.0   # vx
            self.x[3] = 0.0   # vy
            self.initialized = True
            return z[0], z[1]

        # Predict
        x_pred = self.F @ self.x
        P_pred = self.F @ self.P @ self.F.T + self.Q

        # Innovation
        y_innov = z - (self.H @ x_pred)[:2]

        # Innovation covariance
        S = self.H @ P_pred @ self.H.T + self.R

        # Kalman gain
        K = P_pred @ self.H.T @ np.linalg.inv(S)

        # Update state
        self.x = x_pred + K @ y_innov
        self.P = (np.eye(4) - K @ self.H) @ P_pred

        return float(self.x[0]), float(self.x[1])

    def reset(self) -> None:
        """Reset filter state."""
        self.x = np.zeros(4, dtype=np.float32)
        self.P = np.eye(4, dtype=np.float32)
        self.initialized = False


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
    kalman: Optional[SimpleKalmanFilter] = field(default=None, repr=False)

    def __post_init__(self):
        if self.kalman is None:
            self.kalman = SimpleKalmanFilter()


class BagTracker:
    """
    Lightweight tracker for conveyor-bag scenarios with Kalman filtering.
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

        # 1. Predict / age existing tracks using Kalman filter
        for t in self.tracks.values():
            t.age += 1
            t.disappeared += 1
            if t.kalman and t.kalman.initialized:
                # Predict next position
                pred_x, pred_y = t.kalman.predict()
                # Apply prediction to bbox (keep size, move center)
                w = t.bbox[2] - t.bbox[0]
                h = t.bbox[3] - t.bbox[1]
                t.bbox = np.array([
                    pred_x - w / 2,
                    pred_y - h / 2,
                    pred_x + w / 2,
                    pred_y + h / 2,
                ], dtype=np.float32)

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
                # Update Kalman filter with measurement
                center = _box_center(det.bbox)
                smooth_x, smooth_y = t.kalman.update(center) if t.kalman else center

                # Reconstruct bbox from smoothed center
                w = det.bbox[2] - det.bbox[0]
                h = det.bbox[3] - det.bbox[1]
                alpha = 0.7
                t.bbox = np.array([
                    smooth_x - w / 2,
                    smooth_y - h / 2,
                    smooth_x + w / 2,
                    smooth_y + h / 2,
                ], dtype=np.float32)
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
            kalman = SimpleKalmanFilter()
            # Initialize Kalman with first detection
            center = _box_center(det.bbox)
            kalman.update(center)

            t = Track(
                id=self.next_id,
                bbox=det.bbox.copy(),
                last_seen=self.frame_count,
                kalman=kalman,
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
