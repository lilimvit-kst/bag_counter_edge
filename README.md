# Bag Counter Edge — Autonomous CV System for Flour Bag Loading

## Architecture

See `docs/architecture.mmd` for the Mermaid data-flow diagram.

## Directory Structure

```
bag_counter_edge/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── docs/
│   └── architecture.mmd
├── src/
│   ├── __init__.py
│   ├── main.py                     # Pipeline orchestrator
│   ├── config.py                   # Pydantic settings
│   ├── api/
│   │   ├── __init__.py
│   │   └── app.py                  # FastAPI (health, stats)
│   ├── capture/
│   │   ├── __init__.py
│   │   └── camera_stream.py        # RTSP capture (threaded)
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── detector.py             # YOLOv8 bag detector
│   │   ├── tracker.py              # IOU + Kalman-lite tracker
│   │   ├── volume_estimator.py     # Depth / pixel volume proxy
│   │   ├── tripwire.py             # Virtual tripwire logic
│   │   └── handover_logic.py       # Worker handover validation
│   ├── db/
│   │   ├── __init__.py
│   │   └── models.py               # SQLAlchemy ORM
│   ├── nvr/
│   │   ├── __init__.py
│   │   └── clip_recorder.py        # FFmpeg clip cutter
│   ├── training/
│   │   ├── __init__.py
│   │   ├── finetune_yolo.py        # YOLOv8 fine-tuning script
│   │   └── dataset_utils.py        # LabelMe -> YOLO converter
│   └── kiosk/
│       ├── __init__.py
│       └── dashboard.py            # Streamlit operator UI
├── models/                         # YOLO weights (mounted RO)
└── storage/
    ├── clips/                      # 5-second event clips
    ├── db/                         # SQLite
    └── nvr/                        # Continuous 10-min segments
```

## Fine-Tuning YOLOv8 on Your Bags

### 1. Prepare Dataset

Annotate images using **LabelMe** or **CVAT**, then convert to YOLO format:

```bash
python -m src.training.dataset_utils \
    --labelme-dir data/labelme_annotations/ \
    --output-dir data/labels/ \
    --class-map '{"empty_bag":0,"bag_25kg":1,"bag_50kg":2}'
```

Or use the helper programmatically:

```python
from pathlib import Path
from src.training.dataset_utils import convert_labelme_to_yolo, split_dataset, generate_data_yaml

# 1. Convert annotations
convert_labelme_to_yolo(Path("annotations/"), Path("labels/"))

# 2. Split into train/val
split_dataset(Path("images/"), Path("labels/"), Path("data/"), train_ratio=0.8)

# 3. Generate data.yaml
generate_data_yaml(
    Path("data/data.yaml"),
    Path("data"),
    ["empty_bag", "bag_25kg", "bag_50kg"]
)
```

### 2. Train

```bash
python -m src.training.finetune_yolo \
    --data data/data.yaml \
    --model yolov8n.pt \
    --epochs 100 \
    --imgsz 640 \
    --batch 8 \
    --device cpu \
    --project runs/bag_training \
    --name bag_yolo_v1 \
    --export
```

**Key flags:**
- `--model yolov8n.pt` — start from nano (fastest on Edge). Use `s`, `m`, `l` for better accuracy.
- `--device 0` — use GPU if available.
- `--export` — export trained model to ONNX for inference optimization.
- `--copy-best models/best_bag.pt` — automatically copy best weights to project `models/`.

### 3. Augmentations Applied

The training script applies augmentations tuned for industrial conveyor scenarios:
- **Mosaic**: `1.0` (helps with occlusion and overlapping bags)
- **Mixup**: `0.1`
- **HSV**: hue ±1.5%, saturation ±70%, value ±40% (lighting invariant)
- **Scale**: ±50%, **Shear**: ±2°, **Translation**: ±10%
- **RandAugment**: auto policy

---

## Operator Dashboard (Streamlit)

A local web UI for the shift supervisor to monitor counts and control wagons.

### Features
- **Live stats**: total bags, estimated weight, active shift/wagon
- **Class breakdown**: 25 kg / 50 kg / empty counters
- **Event log**: last 30 counted bags with timestamps and clip links
- **Actions**:
  - 🚪 **Close Wagon** — finalize current wagon, save totals
  - 🔄 **Start New Wagon** — begin counting next wagon
  - 🌙 **End Shift** — close shift and start new one

### Run Dashboard

```bash
streamlit run src/kiosk/dashboard.py
```

Open browser at `http://localhost:8501`.

### Docker Compose (with Dashboard)

The `docker-compose.yml` includes a dashboard service. Access at `http://<edge-pc-ip>:8501`.

---

## Edge-Cases & Mitigations

### 1. Worker occludes bag during handover
**Problem:** The worker's body blocks the camera view; the tracker loses the bag or spawns a new ID after occlusion.
**Mitigation:**
- Increase `TRACK_MAX_AGE` (e.g. 30 frames ≈ 1.2 s at 25 FPS) so the track stays alive during brief occlusion.
- Use ROI + disappearance logic: do **not** count until the bag has been missing from the ROI for `HANDOVER_DISAPPEAR_FRAMES` *after* crossing the tripwire. This prevents counting while the bag is merely hidden behind the worker but still in the ROI.
- Optional: add a second camera at a different angle (stereo or side-view) to maintain visibility.

### 2. Double-counting when a bag is shifted but not removed
**Problem:** The worker pushes a bag to the side of the conveyor (it crosses the tripwire) but does not take it into the wagon; later the bag re-enters the ROI.
**Mitigation:**
- Handover logic requires **both** tripwire crossing **and** disappearance from ROI for >= N frames.
- If the bag re-appears inside ROI with the same track ID, `disappeared` counter resets to 0 and `counted` flag remains false.
- Persist track ID in a short-term "ghost" cache (e.g. 5 s) after deletion; if a new detection matches the ghost bbox/position, inherit the old ID and keep `counted=False` if it was not previously counted.

### 3. Empty / flat bags counted as valid 25 kg
**Problem:** A deflated or empty bag rides the conveyor with low volume but is detected as a valid bag.
**Mitigation:**
- Volume estimator classifies bags below `EMPTY_VOLUME_MAX` liters as `BagClass.EMPTY`.
- The pipeline ignores empty bags: they are tracked but `_count_bag()` is never called for `bag_class == "empty"`.
- Add a second validation stage: compare bag aspect ratio. Empty bags often have very high aspect ratio (long and flat). Reject detections where `width / height > 4.0` after tripwire crossing.

## Quick Start

```bash
# 1. Place your fine-tuned YOLO weights into models/
cp your_bag_yolo.pt models/

# 2. Configure environment
cp .env.example .env
# Edit PRIMARY_STREAM_URL, etc.

# 3. Run with Docker Compose
docker compose up --build

# 4. Or run locally
pip install -r requirements.txt
python -m src.main
```
