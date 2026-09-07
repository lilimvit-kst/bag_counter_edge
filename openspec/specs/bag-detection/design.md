# Bag Detection Design

## Current implementation

- `src/pipeline/detector.py` wraps `ultralytics.YOLO`.
- A model path is derived from `settings.MODELS_DIR` and `settings.DETECTION_MODEL`.
- `predict()` invokes Ultralytics inference and converts accepted boxes to immutable `Detection` records containing `[x1,y1,x2,y2]`, confidence, and class ID.
- Runtime filtering uses `settings.BAG_CLASS_IDS`, currently `[0]`.
- Inference currently passes `device="cpu"` unconditionally.

## Important brownfield constraint

Runtime detection presently behaves as a one-class bag detector followed by a separate volume-based `empty/25kg/50kg` classifier. Training utilities currently describe a three-class dataset. Do not change this contract implicitly during model upgrades.
