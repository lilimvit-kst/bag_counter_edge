# Bag Tracking Design

## Current implementation

- `src/pipeline/tracker.py` implements a custom tracker; despite README language, it is not ByteTrack.
- Association is greedy on a matrix of IoU scores and accepts matches above `TRACK_IOU_THRESHOLD`.
- Each track owns a custom constant-velocity `SimpleKalmanFilter` for center smoothing.
- Track state includes ID, bbox, hit count, age/disappearance count, crossing/count flags, confidence, volume/classification, history, and Kalman state.
- Confirmed active tracks require `hits >= TRACK_MIN_HITS`.
- Tracks are deleted when `disappeared > TRACK_MAX_AGE`.

## Coupling warning

`Track.disappeared`, `crossed_tripwire`, and `counted` are consumed directly by counting/handover logic. Replacing the tracker is therefore a behavioral change unless compatibility is explicitly demonstrated.
