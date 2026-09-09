"""
Threaded RTSP/USB capture with frame-drop policy and automatic reconnect.
Keeps only the latest frame to minimize latency on Edge.
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
    Threaded RTSP/USB capture with automatic reconnect on failure.
    Keeps only the latest frame to minimize latency on Edge.
    """

    def __init__(
        self,
        source: str,
        width: int | None = None,
        height: int | None = None,
        fps: int | None = None,
        name: str = "camera",
        max_reconnect_attempts: int | None = None,
        reconnect_delay: float | None = None,
    ) -> None:
        self.source = source
        self.width = width if width is not None else settings.CAMERA_WIDTH
        self.height = height if height is not None else settings.CAMERA_HEIGHT
        self.fps = fps if fps is not None else settings.CAMERA_FPS
        self.name = name
        self.max_reconnect_attempts = (
            max_reconnect_attempts 
            if max_reconnect_attempts is not None 
            else settings.CAMERA_MAX_RECONNECT_ATTEMPTS
        )
        self.reconnect_delay = (
            reconnect_delay 
            if reconnect_delay is not None 
            else settings.CAMERA_RECONNECT_DELAY
        )

        self._cap: Optional[cv2.VideoCapture] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._timestamp: float = 0.0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._reconnect_attempts = 0
        self._last_success_time: float = 0.0
        self.last_frame_monotonic: float = 0.0

    def start(self) -> "CameraStream":
        logger.info(f"[{self.name}] Opening stream: {self.source}")
        self._open_capture()
        if not self._cap or not self._cap.isOpened():
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

    def _open_capture(self) -> bool:
        """Attempt to open the video capture."""
        try:
            self._cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
            if self._cap and self._cap.isOpened():
                self._reconnect_attempts = 0
                logger.info(f"[{self.name}] Stream opened successfully")
                return True
        except Exception as e:
            logger.error(f"[{self.name}] Failed to open stream: {e}")
        return False

    def _reconnect(self) -> bool:
        """Attempt to reconnect to the stream."""
        if self._cap:
            self._cap.release()
            self._cap = None

        if self._reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(
                f"[{self.name}] Max reconnect attempts ({self.max_reconnect_attempts}) reached"
            )
            return False

        self._reconnect_attempts += 1
        logger.warning(
            f"[{self.name}] Reconnecting... (attempt {self._reconnect_attempts}/{self.max_reconnect_attempts})"
        )
        time.sleep(self.reconnect_delay)
        return self._open_capture()

    def _grab_loop(self) -> None:
        """Main capture loop with automatic reconnect."""
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                if not self._reconnect():
                    time.sleep(self.reconnect_delay)
                    continue

            ret, frame = self._cap.read()
            if ret and frame is not None:
                with self._lock:
                    self._latest_frame = frame
                    self._timestamp = time.time()
                self._last_success_time = time.time()
                self.last_frame_monotonic = time.monotonic()
                self._reconnect_attempts = 0
            else:
                logger.warning(f"[{self.name}] Frame grab failed")
                # Check for timeout - if no successful frame for 5 seconds, trigger reconnect
                if time.time() - self._last_success_time > 5.0:
                    logger.error(f"[{self.name}] No frames for 5s, triggering reconnect")
                    if not self._reconnect():
                        time.sleep(self.reconnect_delay)

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
            self._cap = None
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
