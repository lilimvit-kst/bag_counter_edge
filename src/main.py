"""
Main CV pipeline orchestrator.
Runs the detector -> tracker -> volume -> tripwire -> handover loop.
"""
from __future__ import annotations

import signal
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import cv2
import numpy as np
from loguru import logger

from src.config import settings
from src.capture.camera_stream import CameraStream, StereoCapture
from src.pipeline.detector import BagDetector
from src.pipeline.tracker import BagTracker, Track
from src.pipeline.volume_estimator import VolumeEstimator
from src.pipeline.tripwire import Tripwire
from src.pipeline.handover_logic import HandoverLogic
from src.nvr.clip_recorder import ClipRecorder
from src.db.models import init_db, SessionLocal, BagEvent, BagClass, Wagon, Shift


class BagCountingPipeline:
    def __init__(self) -> None:
        logger.info("Initializing Bag Counting Pipeline...")
        init_db()

        # Input
        self.camera = CameraStream(settings.PRIMARY_STREAM_URL, name="primary")
        # If stereo depth needed, swap to StereoCapture()

        # CV modules
        self.detector = BagDetector()
        self.tracker = BagTracker()
        self.volume_est = VolumeEstimator(use_depth=False)
        self.tripwire = Tripwire(y_ratio=settings.TRIPWIRE_Y_RATIO)
        self.handover = HandoverLogic()
        self.clip_recorder = ClipRecorder()

        # State
        self.frame: Optional[np.ndarray] = None
        self.running = False
        self.current_shift: Optional[Shift] = None
        self.current_wagon: Optional[Wagon] = None

        # Ensure active shift/wagon exist (demo: create one if missing)
        self._ensure_shift_wagon()

    def _ensure_shift_wagon(self) -> None:
        db = SessionLocal()
        try:
            shift = db.query(Shift).filter_by(is_active=True).first()
            if not shift:
                shift = Shift(operator_name="auto", is_active=True)
                db.add(shift)
                db.commit()
                db.refresh(shift)
            wagon = db.query(Wagon).filter_by(is_active=True).first()
            if not wagon:
                wagon = Wagon(shift_id=shift.id, wagon_number="W001", is_active=True)
                db.add(wagon)
                db.commit()
                db.refresh(wagon)
            self.current_shift = shift
            self.current_wagon = wagon
        finally:
            db.close()

    def _count_bag(self, track: Track) -> None:
        if track.counted:
            return
        track.counted = True

        bag_class = self.volume_est.classify(track.volume_liters)
        event = BagEvent(
            shift_id=self.current_shift.id if self.current_shift else None,
            wagon_id=self.current_wagon.id if self.current_wagon else None,
            track_id=track.id,
            counted_at=datetime.now(timezone.utc),
            bag_class=BagClass(bag_class),
            estimated_volume_liters=round(track.volume_liters, 2),
            confidence=None,
            bbox_x1=float(track.bbox[0]),
            bbox_y1=float(track.bbox[1]),
            bbox_x2=float(track.bbox[2]),
            bbox_y2=float(track.bbox[3]),
        )

        # Save clip asynchronously / best-effort
        ts = time.time()
        clip_path = self.clip_recorder.save_clip(ts)
        if clip_path:
            event.clip_path = str(clip_path)
            event.clip_start_offset_sec = settings.CLIP_PREROLL_SEC
            event.clip_end_offset_sec = settings.CLIP_POSTROLL_SEC

        db = SessionLocal()
        try:
            db.add(event)
            db.commit()
            logger.success(
                f"BAG COUNTED -> track={track.id}, class={bag_class}, "
                f"vol={track.volume_liters:.1f}L"
            )
        except Exception as e:
            logger.error(f"DB write failed: {e}")
            db.rollback()
        finally:
            db.close()

    def _draw_overlay(self, tracks: list[Track]) -> None:
        h, w = self.frame.shape[:2]
        # ROI
        x1r, y1r, x2r, y2r = (
            settings.ROI_X1_RATIO, settings.ROI_Y1_RATIO,
            settings.ROI_X2_RATIO, settings.ROI_Y2_RATIO,
        )
        cv2.rectangle(
            self.frame,
            (int(x1r * w), int(y1r * h)),
            (int(x2r * w), int(y2r * h)),
            (255, 0, 0), 2,
        )
        # Tripwire
        y_line = self.tripwire.y_px(h)
        cv2.line(self.frame, (0, y_line), (w, y_line), (0, 0, 255), 2)

        for t in tracks:
            x1, y1, x2, y2 = map(int, t.bbox)
            color = (0, 255, 0) if not t.counted else (128, 128, 128)
            label = f"ID:{t.id} {t.bag_class or '?'}"
            cv2.rectangle(self.frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                self.frame, label, (x1, max(20, y1 - 5)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2,
            )

    def run(self) -> None:
        self.running = True
        self.camera.start()
        logger.info("Pipeline started. Press 'q' in preview window to stop.")

        while self.running:
            ok, frame, ts = self.camera.read()
            if not ok or frame is None:
                time.sleep(0.01)
                continue

            self.frame = frame
            h, w = frame.shape[:2]

            # 1. Detect
            detections = self.detector.predict(frame)

            # 2. Track
            tracks = self.tracker.update(detections)

            # 3. Volume + classify per track (once)
            for t in tracks:
                if t.volume_liters == 0.0:
                    # Find matching detection for volume
                    for d in detections:
                        iou = self._iou(t.bbox, d.bbox)
                        if iou > 0.5:
                            vol = self.volume_est.estimate(frame, d, depth_map=None)
                            t.volume_liters = vol
                            t.bag_class = self.volume_est.classify(vol)
                            break

            # 4. Tripwire + handover
            for t in tracks:
                just_crossed, below = self.tripwire.check_crossing(t, h)
                if just_crossed:
                    t.crossed_tripwire = True
                    logger.info(f"Track {t.id} crossed tripwire")

                if self.handover.evaluate(t, w, h):
                    self._count_bag(t)

            # 5. Visualise
            self._draw_overlay(tracks)
            cv2.imshow("Bag Counter Edge", self.frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                self.running = False

        self.shutdown()

    def _iou(self, a: np.ndarray, b: np.ndarray) -> float:
        x1 = max(a[0], b[0]); y1 = max(a[1], b[1])
        x2 = min(a[2], b[2]); y2 = min(a[3], b[3])
        inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        area_a = (a[2] - a[0]) * (a[3] - a[1])
        area_b = (b[2] - b[0]) * (b[3] - b[1])
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    def shutdown(self) -> None:
        logger.info("Shutting down pipeline...")
        self.camera.stop()
        cv2.destroyAllWindows()


def main() -> None:
    pipeline = BagCountingPipeline()

    def _sig_handler(signum, frame):
        logger.warning(f"Signal {signum} received, stopping...")
        pipeline.running = False

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    pipeline.run()


if __name__ == "__main__":
    main()
