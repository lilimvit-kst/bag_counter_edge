"""Bounded latest-state telemetry; network and JPEG work stay off the CV loop."""
import base64
import copy
import json
import threading
import time
import uuid
from functools import wraps
from datetime import datetime, timezone

MESSAGES = {'camera': 'Camera signal interrupted', 'processing': 'Bag processing interrupted',
            'persistence': 'A bag count could not be saved', 'startup': 'Counting model could not start'}


def best_effort(method):
    """Observability must not turn a successful count into a pipeline failure."""
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except Exception:
            return None
    return wrapped


def stamp():
    return datetime.now(timezone.utc).isoformat()


def runtime_key(source):
    return f'bag-dashboard:{source}:runtime'


def channel(source):
    return f'bag-dashboard:{source}:changed'


class RuntimePublisher:
    def __init__(self, url, source='primary', ttl=5, interval=0.5, client=None):
        self.url, self.source, self.ttl, self.interval = url, source, ttl, interval
        self.client = client
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.started = time.monotonic()
        self.progress = {}
        self.camera_clock = lambda: 0.0
        self.data = {'source': source, 'run_id': str(uuid.uuid4()), 'state': 'starting',
                     'last_detection': None, 'alerts': [], 'active_tracks': 0}
        self.thumbnail = None  # Only one bounded crop is retained.

    @best_effort
    def start(self, camera_clock=lambda: 0.0):
        self.camera_clock = camera_clock
        self.thread = threading.Thread(target=self._loop, daemon=True, name='dashboard-telemetry')
        self.thread.start()

    @best_effort
    def update(self, **fields):
        with self.lock:
            self.data.update(fields)

    @best_effort
    def completed(self, stage):
        with self.lock:
            self.progress[stage] = time.monotonic()

    @best_effort
    def alert(self, code, active=True):
        with self.lock:
            item = next((a for a in self.data['alerts'] if a['code'] == code), None)
            if item is None:
                if not active:
                    return
                item = {'code': code, 'message': MESSAGES.get(code, 'Counting needs attention'),
                        'first_at': stamp(), 'count': 0, 'severity': 'error' if code != 'camera' else 'warning'}
                self.data['alerts'] = (self.data['alerts'] + [item])[-8:]
            if not active and not item.get('active', False):
                return
            if active:
                item['count'] += 1
            item.update(active=active, last_at=stamp())

    @best_effort
    def observe(self, frame, detections, tracks, captured_at):
        now = time.monotonic()
        if captured_at == getattr(self, 'last_capture', None):
            return
        self.last_capture = captured_at
        observed = [t for t in tracks if t.disappeared == 0]
        track = max(observed, key=lambda t: t.id) if observed else None
        det = max(detections, key=lambda d: d.confidence) if detections else None
        if track is None and det is None:
            return
        box = track.bbox if track is not None else det.bbox
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = map(int, box)
        # Stride sampling caps the copied image before it enters the worker.
        crop = frame[max(0,y1):max(0,min(h,y2)), max(0,x1):max(0,min(w,x2))]
        image = None
        if crop.size:
            step = max(1, (max(crop.shape[:2]) + 191) // 192)
            image = crop[::step, ::step].copy()
        detection = {'track_id': track.id if track is not None else None,
                     'observed_at': datetime.fromtimestamp(captured_at, timezone.utc).isoformat(),
                     'class': track.bag_class if track is not None else None,
                     'state': 'Waiting for handover' if track is not None and track.crossed_tripwire else 'Detected',
                     'thumbnail': None}
        with self.lock:
            previous = self.data['last_detection']
            if previous and track is not None and previous['track_id'] == track.id and previous['state'] == 'Count saved':
                detection['state'] = 'Count saved'
            self.data['last_detection'] = detection
            self.progress['detection'] = now
            self.thumbnail = image

    @best_effort
    def saved(self, track_id, event_id):
        with self.lock:
            self.data['last_event_id'] = event_id
            last = self.data['last_detection']
            if last and last['track_id'] == track_id:
                last['state'] = 'Count saved'
        self.alert('persistence', False)

    def payload(self):
        now = time.monotonic()
        with self.lock:
            data = copy.deepcopy(self.data)
            data['ages'] = {key: max(0, now-value) for key, value in self.progress.items()}
            data['uptime'] = now - self.started
            image, self.thumbnail = self.thumbnail, None
        camera_at = self.camera_clock()
        data['camera_age'] = max(0, now-camera_at) if camera_at else None
        data['published_at'] = stamp()
        data['ttl'] = self.ttl
        if image is not None:
            import cv2
            ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 65])
            if ok and len(encoded) <= 40000:
                thumbnail = 'data:image/jpeg;base64,' + base64.b64encode(encoded).decode('ascii')
                data['last_detection']['thumbnail'] = thumbnail
                with self.lock:
                    if self.data['last_detection']['observed_at'] == data['last_detection']['observed_at']:
                        self.data['last_detection']['thumbnail'] = thumbnail
        if data['ages'].get('detection', 0) > 30 and data['last_detection']:
            data['last_detection']['thumbnail'] = None
        return data

    def _loop(self):
        try:
            if self.client is None:
                import redis
                self.client = redis.Redis.from_url(self.url, socket_timeout=0.25, socket_connect_timeout=0.25)
            while True:
                try:
                    data = self.payload()
                    pipe = self.client.pipeline(transaction=True)
                    pipe.set(runtime_key(self.source), json.dumps(data), ex=self.ttl)
                    pipe.publish(channel(self.source), data['run_id'])
                    pipe.execute()
                except Exception:
                    # UI detects unavailable telemetry; raw network errors never enter operator data.
                    pass
                if self.stop_event.is_set():
                    break
                self.stop_event.wait(self.interval)
        finally:
            if self.client is not None:
                self.client.close()

    @best_effort
    def close(self, state='stopped'):
        self.update(state=state)
        # Best effort final state; expiry still handles abrupt process death.
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=0.75)


def derive_status(data, available=True, camera_deadline=5, stage_deadline=15):
    if not available:
        return {'state': 'unavailable', 'label': 'Status unavailable', 'camera': 'Unknown',
                'detector': 'Unknown', 'tracker': 'Unknown', 'reason': 'Live status is unavailable'}
    if not data:
        return {'state': 'offline', 'label': 'Offline', 'camera': 'Unknown',
                'detector': 'Stopped', 'tracker': 'Stopped', 'reason': 'Counting service is not reporting'}
    state = data['state']
    camera_age = data.get('camera_age')
    camera = 'Connected' if camera_age is not None and camera_age < camera_deadline else 'Unavailable'
    ages = data.get('ages', {})
    stalled = any(ages.get(s, data.get('uptime', 0)) > stage_deadline for s in ('detector', 'tracker'))
    if state in ('fault', 'stopped'):
        label, reason = 'Offline', 'Counting service stopped' if state == 'stopped' else 'Bag processing interrupted'
        state = 'offline'
    elif state == 'starting':
        label, reason = 'Starting', 'Initializing counting model'
    elif camera == 'Unavailable':
        state, label, reason = 'online', 'Online', 'Counting interrupted: camera unavailable'
    elif stalled:
        state, label, reason = 'offline', 'Offline', 'Bag processing stalled'
    else:
        state, label, reason = 'online', 'Online', 'Counting active' if data.get('active_tracks') else 'Waiting for bags'
    component = 'Running' if state == 'online' else ('Starting' if state == 'starting' else 'Stopped')
    return {'state': state, 'label': label, 'camera': camera, 'detector': component,
            'tracker': component, 'reason': reason, 'updated_at': data.get('published_at')}
