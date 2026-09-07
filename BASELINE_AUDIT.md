# Bag Counter Edge — Baseline Audit

This file records observations from the source tree used to build the initial OpenSpec baseline. It is **not** a desired-behavior specification. Items here should be addressed through explicit OpenSpec changes rather than silently normalized into baseline requirements.

## Scope reviewed

The baseline was derived from the current source under `src/`, tests, `.env.example`, Docker Compose files, and README/deployment documentation. Code was treated as implementation truth where documentation conflicted with runtime behavior.

## High-priority discrepancies and defects

1. **Tracker naming vs implementation.** README describes enhanced ByteTrack, while `src/pipeline/tracker.py` explicitly implements greedy IoU association plus a custom Kalman filter and states that a production tracker should replace it.
2. **Broken Celery clip task path.** `process_clip_task()` calls `ClipRecorder._extract_clip()`, but the current `ClipRecorder` exposes `save_clip()` and `_save_clip_sync()`; `_extract_clip()` is absent.
3. **OAuth2 login contract is incomplete.** FastAPI configures `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")`, but the application currently has no `/api/v1/auth/login` route. Protected task endpoints can validate externally-created JWTs, but the service cannot issue them through the advertised token URL.
4. **Runtime detector class model differs from training example.** Runtime accepts `BAG_CLASS_IDS=[0]` as one `flour_bag` detector class and classifies size/empty status afterward by estimated volume. Training/dataset helpers define three annotation classes (`empty_bag`, `bag_25kg`, `bag_50kg`). This is an architectural mismatch that must be resolved before retraining/migrating models.
5. **YOLO model path semantics are inconsistent.** `Settings.DETECTION_MODEL` is joined with `MODELS_DIR`, while `.env.example` sets `YOLO_MODEL_PATH=models/yolov8n.pt`; depending on Pydantic alias behavior/version, this can produce an unintended `models/models/...` path. Verify in the deployed environment before relying on the setting.
6. **Inference hardware configuration is not wired through.** `BagDetector.predict()` forces `device="cpu"`, while Docker Compose requests all GPUs and `.env.example` exposes CUDA-related variables not consumed by `Settings`/detector.
7. **Handover logic depends on tracker disappearance semantics.** Counting requires a crossed track to be outside ROI with `track.disappeared >= HANDOVER_DISAPPEAR_FRAMES`. Any tracker replacement can therefore change counting behavior even if detector accuracy improves.
8. **"Today" stats are not date-scoped.** `/api/v1/stats/today` currently counts all `BagEvent` rows in the database.
9. **CORS config is broader than documented configuration.** API currently allows all origins regardless of `.env.example`'s `API_CORS_ORIGINS` value.
10. **Configuration surface exceeds consumed settings.** `.env.example` documents several variables that are not represented or used by `Settings`/runtime code (for example `ENVIRONMENT`, `DEBUG`, `DATABASE_URL`, `DETECT_CLASSES`, `USE_CUDA`, `CUDA_DEVICE`, and others).

## Testing gaps

Current tests primarily cover selected API authentication/task behavior and notification formatting/delivery mocks. There are no focused tests for detector filtering, tracker identity stability, tripwire crossing direction, handover confirmation, duplicate-count prevention, volume thresholds, camera reconnect behavior, event persistence, NVR/clip extraction, or end-to-end counting from prerecorded video.

## Recommended first OpenSpec changes

The safest first change is **not** a wholesale model migration. Recommended sequence:

1. `stabilize-counting-contract-tests` — add deterministic tests around tripwire, tracker/handover, and exactly-once BagEvent creation.
2. `align-runtime-model-class-contract` — decide whether detection is one class (`flour_bag`) plus volume classification or three YOLO classes; make training/runtime consistent.
3. `fix-background-clip-processing` — repair Celery clip extraction contract and ensure DB clip paths represent actual or explicitly pending artifacts.
4. `complete-api-authentication` — add a real login/token issuance flow or remove the misleading OAuth2 token URL contract.
5. `migrate-detector-model` — only then perform the YOLO generation/model migration with measured accuracy and hardware impact.

## Baseline philosophy

The `specs/` directory describes stable, observable contracts that the current product is trying to provide. Known defects above are deliberately not promoted into normative requirements. A future change should state whether it fixes a defect, intentionally alters behavior, or merely refactors internals.
