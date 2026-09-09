import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import fakeredis
import numpy as np
import pytest

from src.dashboard.telemetry import RuntimePublisher, derive_status, runtime_key


def test_brief_detection_is_retained_between_publications(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr('src.dashboard.telemetry.time.monotonic', lambda: clock[0])
    publisher = RuntimePublisher('unused')
    assert publisher.interval == .5
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    publisher.observe(frame, [], [], 100)
    publisher.payload()
    clock[0] = 100.1
    frame[10:50, 10:50] = 255
    det = SimpleNamespace(confidence=.9, bbox=[10, 10, 50, 50])
    publisher.observe(frame, [det], [], 100.1)
    frame[:] = 0  # the retained crop owns its pixels
    clock[0] = 100.6
    publisher.observe(frame, [], [], 100.6)
    payload = publisher.payload()
    last = payload['last_detection']
    assert last['observed_at'] == '1970-01-01T00:01:40.100000+00:00'
    assert last['track_id'] is None and last['class'] is None
    assert last['state'] == 'Detected' and 'last_event_id' not in payload
    import base64
    import cv2
    decoded = cv2.imdecode(np.frombuffer(base64.b64decode(last['thumbnail'].split(',')[1]), np.uint8), cv2.IMREAD_COLOR)
    assert decoded.mean() > 250
    clock[0] = 131
    assert publisher.payload()['last_detection']['thumbnail'] is None


def test_status_transitions():
    data = {'state': 'running', 'camera_age': 0.1, 'ages': {'detector': 0.1, 'tracker': 0.1}, 'uptime': 20}
    assert derive_status(data)['state'] == 'online'
    assert derive_status(data)['reason'] == 'Waiting for bags'
    assert derive_status({**data, 'camera_age': 10})['reason'] == 'Counting interrupted: camera unavailable'
    assert derive_status({**data, 'ages': {'detector': 20, 'tracker': 20}})['state'] == 'offline'
    assert derive_status({**data, 'state': 'starting'})['state'] == 'starting'
    assert derive_status({**data, 'state': 'fault'})['state'] == 'offline'
    assert derive_status(None)['state'] == 'offline'
    assert derive_status(None, available=False)['state'] == 'unavailable'


def test_thumbnail_selection_expiry_and_saved_state(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr('src.dashboard.telemetry.time.monotonic', lambda: clock[0])
    publisher = RuntimePublisher('unused')
    frame = np.zeros((600, 1000, 3), dtype=np.uint8)
    det = SimpleNamespace(confidence=.9, bbox=np.array([10, 20, 800, 580]))
    track = SimpleNamespace(id=1, bbox=det.bbox, disappeared=0, crossed_tripwire=True, bag_class=None)
    publisher.observe(frame, [det], [], 100)
    assert publisher.payload()['last_detection']['track_id'] is None
    clock[0] += 1
    publisher.observe(frame, [det], [track], 101)
    assert max(publisher.thumbnail.shape[:2]) <= 192
    payload = publisher.payload()
    assert payload['last_detection']['class'] is None
    assert payload['last_detection']['thumbnail'].startswith('data:image/jpeg;base64,')
    publisher.saved(1, 7)
    assert publisher.payload()['last_detection']['state'] == 'Count saved'
    clock[0] += 31
    assert publisher.payload()['last_detection']['thumbnail'] is None
    publisher.observe(frame, [det], [track], 101)  # repeated cached capture is not a new observation
    assert publisher.payload()['last_detection']['observed_at'] == payload['last_detection']['observed_at']
    clock[0] += 1
    publisher.observe(frame, [], [], 102)
    assert publisher.payload()['last_detection']['track_id'] == 1


def test_alerts_group_recovery_and_safe_input():
    publisher = RuntimePublisher('unused')
    for _ in range(100):
        publisher.alert('persistence')
    publisher.alert('persistence', False)
    alert = publisher.payload()['alerts'][0]
    assert alert['count'] == 100 and alert['active'] is False
    publisher.observe(None, [], [], 0)  # telemetry failure cannot interrupt counting
    assert len(publisher.payload()['alerts']) == 1


def test_multiple_detection_candidates_ignore_disappeared_tracks():
    publisher = RuntimePublisher('unused', interval=0)
    frame = np.zeros((100,100,3), dtype=np.uint8)
    def track(identity, missing=0):
        return SimpleNamespace(id=identity, bbox=np.array([10,10,50,80]),
                               disappeared=missing, crossed_tripwire=False, bag_class='25kg')
    publisher.observe(frame, [], [track(1), track(3), track(9, missing=1)], time.time())
    assert publisher.payload()['last_detection']['track_id'] == 3


def test_slow_network_never_blocks_producer():
    entered, release = threading.Event(), threading.Event()
    client = Mock()
    pipe = client.pipeline.return_value
    def execute():
        entered.set()
        release.wait(2)
        raise ConnectionError('test outage')
    pipe.execute.side_effect = execute
    publisher = RuntimePublisher('unused', client=client)
    publisher.start()
    assert entered.wait(1)
    start = time.monotonic()
    for i in range(1000):
        publisher.update(active_tracks=i)
        publisher.completed('detector')
    assert time.monotonic()-start < .2
    assert publisher.data['active_tracks'] == 999
    release.set()
    publisher.close()
    assert not publisher.thread.is_alive()


def test_publication_and_shutdown():
    server = fakeredis.FakeServer()
    producer = fakeredis.FakeRedis(server=server)
    reader = fakeredis.FakeRedis(server=server)
    publisher = RuntimePublisher('unused', client=producer, interval=.01)
    publisher.start(time.monotonic)
    for _ in range(100):
        if reader.get(runtime_key('primary')):
            break
        time.sleep(.01)
    publisher.update(state='running')
    publisher.close()
    assert json.loads(reader.get(runtime_key('primary')))['state'] == 'stopped'
    assert reader.ttl(runtime_key('primary')) > 0


@pytest.mark.asyncio
async def test_runtime_expiry_and_transport_failure(monkeypatch):
    import fakeredis.aioredis
    from src.dashboard import api
    server = fakeredis.FakeServer()
    client = fakeredis.aioredis.FakeRedis(server=server)
    data = {'state':'running','camera_age':0,'ages':{'detector':0,'tracker':0},'uptime':1,'ttl':5}
    await client.set(runtime_key('primary'), json.dumps(data), px=3000)
    monkeypatch.setattr(api, 'redis_client', lambda: fakeredis.aioredis.FakeRedis(server=server))
    result = await api.runtime()
    assert result['data']['camera_age'] >= 2
    assert result['status']['state'] == 'online'
    await client.delete(runtime_key('primary'))
    assert (await api.runtime())['status']['state'] == 'offline'
    server.connected = False
    assert (await api.runtime())['status']['state'] == 'unavailable'
