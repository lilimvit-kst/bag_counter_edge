# Bag Classification Design

## Current implementation

- `src/pipeline/volume_estimator.py` owns `VolumeEstimator`.
- The pipeline instantiates it with `use_depth=False`.
- Monocular fallback uses `bbox_area / 500.0` as an empirical liters proxy.
- Depth mode estimates width/height from focal length and median depth, approximates thickness as 25% of height, then converts cubic meters to liters.
- Classification thresholds are `EMPTY_VOLUME_MAX` and `VOLUME_25KG_MAX`.

## Calibration warning

The pixel-to-volume factor is camera-geometry dependent. Model migration should not be assumed to preserve bounding-box geometry closely enough to keep existing thresholds calibrated.
