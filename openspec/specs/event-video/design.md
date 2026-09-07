# Event Video Design

## Current implementation

- `src/nvr/clip_recorder.py` provides `NVRRecorder` and `ClipRecorder` using FFmpeg subprocesses.
- `ClipRecorder` owns a `ThreadPoolExecutor`; `save_clip()` computes the output path and submits `_save_clip_sync()`.
- Without a source file, clip extraction falls back to a live RTSP FFmpeg read and may not contain true pre-roll.
- Docker Compose also provides a dedicated `nvr` FFmpeg container writing ten-minute-style segments to `storage/nvr` based on configured duration.

## Known defect

`src/tasks/tasks.py::process_clip_task()` calls a nonexistent `ClipRecorder._extract_clip()` method. This is tracked in `openspec/BASELINE_AUDIT.md` and intentionally is not described as required behavior.
