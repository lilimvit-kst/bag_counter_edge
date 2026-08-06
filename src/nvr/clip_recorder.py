"""
NVR continuous recording and event-based clip extraction.
Uses FFmpeg for low-overhead segmented recording.
"""
from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger

from src.config import settings


class NVRRecorder:
    """
    Continuously records RTSP to 10-minute MP4 segments.
    Old segments are purged after NVR_RETENTION_DAYS.
    """

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = output_dir or settings.STORAGE_DIR / "nvr"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.segment_time = settings.NVR_SEGMENT_MINUTES
        self.retention_days = settings.NVR_RETENTION_DAYS
        self.process: Optional[subprocess.Popen] = None

    def start(self) -> None:
        pattern = str(self.output_dir / "%Y%m%d_%H%M%S.mp4")
        cmd = [
            "ffmpeg",
            "-hide_banner", "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-i", settings.PRIMARY_STREAM_URL,
            "-c", "copy",
            "-f", "segment",
            "-segment_time", str(self.segment_time * 60),
            "-strftime", "1",
            "-reset_timestamps", "1",
            pattern,
        ]
        logger.info(f"Starting NVR: {' '.join(cmd)}")
        self.process = subprocess.Popen(cmd)

    def stop(self) -> None:
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            logger.info("NVR stopped.")

    def purge_old(self) -> None:
        now = time.time()
        for f in self.output_dir.glob("*.mp4"):
            if (now - f.stat().st_mtime) > (self.retention_days * 86400):
                f.unlink(missing_ok=True)


class ClipRecorder:
    """
    Extracts a 5-second event clip from the continuous NVR segments
    or directly from a rolling RAM buffer (simpler for Edge).
    """

    def __init__(self, clips_dir: Optional[Path] = None) -> None:
        self.clips_dir = clips_dir or settings.CLIPS_DIR
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        self.pre = settings.CLIP_PREROLL_SEC
        self.post = settings.CLIP_POSTROLL_SEC

    def save_clip(
        self,
        event_ts: float,
        source_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        Extract clip around event_ts.
        If source_path is None, uses direct FFmpeg from RTSP (fallback).
        """
        start = max(0.0, event_ts - self.pre)
        duration = self.pre + self.post
        stamp = datetime.fromtimestamp(event_ts, tz=timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        out_path = self.clips_dir / f"bag_event_{stamp}.mp4"

        if source_path and source_path.exists():
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-ss", str(start), "-t", str(duration),
                "-i", str(source_path),
                "-c", "copy", "-y", str(out_path),
            ]
        else:
            # Direct fallback from live stream (may miss exact frame)
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-rtsp_transport", "tcp",
                "-i", settings.PRIMARY_STREAM_URL,
                "-t", str(duration),
                "-c", "copy", "-y", str(out_path),
            ]

        try:
            subprocess.run(cmd, check=True, timeout=15)
            logger.info(f"Clip saved: {out_path}")
            return out_path
        except Exception as e:
            logger.error(f"Clip extraction failed: {e}")
            return None
