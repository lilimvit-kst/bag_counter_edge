# Camera Capture Design

## Current implementation

- `src/capture/camera_stream.py` owns `CameraStream`, using OpenCV `VideoCapture` and a background grab loop.
- `CameraStream.read()` exposes the most recently captured frame and timestamp rather than blocking the pipeline on each camera read.
- Reconnect behavior is controlled by `CAMERA_RECONNECT_DELAY` and `CAMERA_MAX_RECONNECT_ATTEMPTS`.
- `StereoCapture` composes two `CameraStream` instances and exposes a synchronized-read abstraction.
- The primary pipeline currently instantiates only one `CameraStream`; stereo/depth is not active in `BagCountingPipeline`.

## Constraints

Camera loss must not cause duplicate counting when a stream returns. Any future buffering or reconnection redesign must preserve track/count lifecycle semantics or explicitly reset them in a documented way.
