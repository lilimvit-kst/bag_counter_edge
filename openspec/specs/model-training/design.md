# Model Training Design

## Current implementation

- `src/training/dataset_utils.py` currently maps `empty_bag -> 0`, `bag_25kg -> 1`, `bag_50kg -> 2`, converts LabelMe rectangles/polygons to bounding boxes, splits data, and generates `data.yaml`.
- `src/training/finetune_yolo.py` is explicitly YOLOv8-oriented in naming/default weights, though it delegates training/export to the installed Ultralytics package.
- Training exposes epochs, image size, batch, workers, device, learning-rate settings, augmentation parameters, resume, ONNX export, INT8 export, and best-weight copy destination.

## Critical compatibility decision

Current runtime detection expects configured detector bag class IDs and separately applies volume classification. The training helper's three-class dataset contract is therefore not automatically compatible with runtime semantics. Resolve this before new training is treated as production-ready.
