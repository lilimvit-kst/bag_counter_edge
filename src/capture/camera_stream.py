"""
Camera capture module.
Supports single RGB stream and optional stereo/depth pair.
"""
from __future__ import annotations

import threading
import time
from queue import Queue, Empty
from typing import Optional

import cv2
import numpy as np
from loguru import logger

from src.config import settings


class CameraStream:
    """
    Threaded RTSP/USB capture with frame-drop policy.
    Keeps only the latest frame to minimize latency on Edge.
    """

    def __init__(
        self,
        source: str,
        width: int = settings.FRAME_WIDTH,
        height: int = settings.FRAME_HEIGHT,
        fps: int = settings.FPS,
        name: str = "camera",
    ) -> None:
        self.source = source
        self.width = width
        self.height = height
        self.fps = fps
        self.name = name

        self._cap: Optional[cv2.VideoCapture] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._timestamp: float = 0.0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self) -> "CameraStream":
        logger.info(f"[{self.name}] Opening stream: {self.source}")
        self._cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera stream: {self.source}")

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)

        self._running = True
        self._thread = threading.Thread(target=self._grab_loop, daemon=True)
        self._thread.start()
        # Warm-up
        time.sleep(1.0)
        return self

    def _grab_loop(self) -> None:
        while self._running and self._cap is not None:
            ret, frame = self._cap.read()
            if ret and frame is not None:
                with self._lock:
                    self._latest_frame = frame
                    self._timestamp = time.time()
            else:
                logger.warning(f"[{self.name}] Frame grab failed, retrying...")
                time.sleep(0.01)

    def read(self) -> tuple[bool, Optional[np.ndarray], float]:
        with self._lock:
            if self._latest_frame is None:
                return False, None, 0.0
            frame = self._latest_frame.copy()
            ts = self._timestamp
        return True, frame, ts

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._cap:
            self._cap.release()
        logger.info(f"[{self.name}] Stream stopped.")

    def __enter__(self) -> "CameraStream":
        return self.start()

    def __exit__(self, *args) -> None:
        self.stop()


class StereoCapture:
    """
    Synchronised stereo capture for depth-from-stereo.
    """

    def __init__(self) -> None:
        self.left = CameraStream(
            settings.PRIMARY_STREAM_URL,
            name="left",
        )
        self.right = CameraStream(
            settings.SECONDARY_STREAM_URL,
            name="right",
        )

    def start(self) -> "StereoCapture":
        self.left.start()
        self.right.start()
        return self

    def read_sync(self, timeout_sec: float = 0.5) -> tuple[bool, Optional[np.ndarray], Optional[np.ndarray], float]:
        """Return paired left/right frames with best-effort sync."""
        ok_l, frame_l, ts_l = self.left.read()
        ok_r, frame_r, ts_r = self.right.read()
        if not ok_l or not ok_r:
            return False, None, None, 0.0
        # Simple sync: if drift > threshold, drop and retry once
        if abs(ts_l - ts_r) > timeout_sec:
            time.sleep(0.05)
            ok_r, frame_r, ts_r = self.right.read()
        return True, frame_l, frame_r, (ts_l + ts_r) / 2.0

    def stop(self) -> None:
        self.left.stop()
        self.right.stop()
