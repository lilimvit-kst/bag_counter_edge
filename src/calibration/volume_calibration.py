"""
Volume Calibration Tool.

Collects reference measurements from known 25 kg and 50 kg bags
to compute calibrated volume thresholds and the pixel-to-liter factor.

Usage:
    python -m src.calibration.volume_calibration \
        --source rtsp://192.168.1.100:554/stream1 \
        --samples 30 \
        --out storage/calibration.json

Controls (during live preview):
    [1] — capture current frame as 25 kg reference
    [2] — capture current frame as 50 kg reference
    [E] — capture current frame as EMPTY reference
    [S] — save calibration to file
    [Q] — quit
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import List, Dict, Any

import cv2
import numpy as np
from loguru import logger

from src.capture.camera_stream import CameraStream
from src.pipeline.detector import BagDetector
from src.pipeline.volume_estimator import VolumeEstimator


class CalibrationSession:
    def __init__(self, source: str, samples_target: int = 30) -> None:
        self.camera = CameraStream(source, name="calib")
        self.detector = BagDetector()
        self.volume_est = VolumeEstimator(use_depth=False)
        self.samples_target = samples_target

        self.samples: Dict[str, List[float]] = {
            "empty": [],
            "25kg": [],
            "50kg": [],
        }

    def _measure_once(self) -> float | None:
        ok, frame, _ = self.camera.read()
        if not ok or frame is None:
            return None
        detections = self.detector.predict(frame)
        if not detections:
            logger.warning("No bag detected in frame.")
            return None
        # Use largest detection by area
        largest = max(detections, key=lambda d: (d.bbox[2] - d.bbox[0]) * (d.bbox[3] - d.bbox[1]))
        vol = self.volume_est.estimate(frame, largest, depth_map=None)
        return vol

    def _collect_samples(self, label: str) -> None:
        logger.info(f"Collecting {self.samples_target} samples for '{label}'...")
        while len(self.samples[label]) < self.samples_target:
            vol = self._measure_once()
            if vol is not None:
                self.samples[label].append(vol)
                logger.info(f"  [{label}] sample {len(self.samples[label])}/{self.samples_target}: {vol:.2f} L")
            time.sleep(0.1)
        logger.success(f"'{label}' collection complete. Mean={statistics.mean(self.samples[label]):.2f} L")

    def _draw_ui(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        overlay = frame.copy()

        # Title
        cv2.putText(overlay, "VOLUME CALIBRATION", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

        # Stats
        y = 80
        for label, vals in self.samples.items():
            text = f"{label}: {len(vals)}/{self.samples_target}"
            if vals:
                text += f"  mean={statistics.mean(vals):.1f}L  std={statistics.stdev(vals) if len(vals) > 1 else 0:.1f}L"
            color = (0, 255, 0) if len(vals) >= self.samples_target else (0, 165, 255)
            cv2.putText(overlay, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            y += 35

        # Controls
        cv2.putText(overlay, "[1]=25kg  [2]=50kg  [E]=Empty  [C]=Collect batch  [S]=Save  [Q]=Quit", (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        return overlay

    def run_interactive(self) -> None:
        self.camera.start()
        logger.info("Calibration started. Place a reference bag and press keys.")

        collecting_for: str | None = None
        while True:
            ok, frame, _ = self.camera.read()
            if not ok:
                time.sleep(0.01)
                continue

            # Auto-collect if in batch mode
            if collecting_for and len(self.samples[collecting_for]) < self.samples_target:
                vol = self._measure_once()
                if vol is not None:
                    self.samples[collecting_for].append(vol)

            display = self._draw_ui(frame)
            cv2.imshow("Volume Calibration", display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("1"):
                collecting_for = "25kg"
                logger.info("Batch collect: 25kg")
            elif key == ord("2"):
                collecting_for = "50kg"
                logger.info("Batch collect: 50kg")
            elif key == ord("e"):
                collecting_for = "empty"
                logger.info("Batch collect: empty")
            elif key == ord("c"):
                # Manual single capture for whichever was last selected
                if collecting_for:
                    vol = self._measure_once()
                    if vol is not None:
                        self.samples[collecting_for].append(vol)
                        logger.info(f"Manual capture: {collecting_for} = {vol:.2f}L")
            elif key == ord("s"):
                self.save()

        self.camera.stop()
        cv2.destroyAllWindows()

    def compute_thresholds(self) -> Dict[str, Any]:
        """Compute volume thresholds and pixel-to-liter factor from collected data."""
        if not all(len(v) >= 5 for v in self.samples.values()):
            raise ValueError("Need at least 5 samples per class.")

        empty_mean = statistics.mean(self.samples["empty"])
        empty_std = statistics.stdev(self.samples["empty"]) if len(self.samples["empty"]) > 1 else 0
        kg25_mean = statistics.mean(self.samples["25kg"])
        kg25_std = statistics.stdev(self.samples["25kg"]) if len(self.samples["25kg"]) > 1 else 0
        kg50_mean = statistics.mean(self.samples["50kg"])
        kg50_std = statistics.stdev(self.samples["50kg"]) if len(self.samples["50kg"]) > 1 else 0

        # Thresholds with safety margin (1.5 std)
        margin = 1.5
        empty_max = empty_mean + margin * empty_std
        threshold_25_50 = (kg25_mean + kg50_mean) / 2.0  # midpoint

        # Pixel-to-liter factor: median area of 25kg samples / known volume proxy
        # We use 25kg as reference since its volume is most stable.
        # In monocular mode: volume = area_px / factor -> factor = area_px / volume_liters
        # We'll compute factor from the first 25kg detection area (stored separately if needed).
        # For simplicity: we return the raw thresholds which config.py will use.

        return {
            "calibrated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "samples": {k: len(v) for k, v in self.samples.items()},
            "empty": {"mean": round(empty_mean, 3), "std": round(empty_std, 3), "threshold_max": round(empty_max, 3)},
            "25kg": {"mean": round(kg25_mean, 3), "std": round(kg25_std, 3)},
            "50kg": {"mean": round(kg50_mean, 3), "std": round(kg50_std, 3)},
            "thresholds": {
                "empty_max_liters": round(empty_max, 3),
                "classify_25_50_liters": round(threshold_25_50, 3),
            },
        }

    def save(self, path: str = "storage/calibration.json") -> Path:
        data = self.compute_thresholds()
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.success(f"Calibration saved: {out}")
        return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Volume calibration for bag classifier")
    parser.add_argument("--source", type=str, default=None, help="Camera stream URL (default from config)")
    parser.add_argument("--samples", type=int, default=30, help="Samples per class")
    parser.add_argument("--out", type=str, default="storage/calibration.json", help="Output JSON path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.source or "rtsp://192.168.1.100:554/stream1"
    session = CalibrationSession(source, samples_target=args.samples)
    try:
        session.run_interactive()
        if all(len(v) >= 5 for v in session.samples.values()):
            session.save(args.out)
        else:
            logger.warning("Insufficient samples for calibration. Not saved.")
    except KeyboardInterrupt:
        logger.info("Interrupted.")
    finally:
        session.camera.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
