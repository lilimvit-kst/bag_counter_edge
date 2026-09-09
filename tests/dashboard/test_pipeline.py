import importlib
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.dashboard import queries
from src.dashboard.telemetry import RuntimePublisher


@pytest.fixture
def pipeline_module(monkeypatch):
    # Inference is a deterministic boundary fixture; no weights or camera are loaded.
    if importlib.util.find_spec('ultralytics') is None:
        monkeypatch.setitem(sys.modules, 'ultralytics', SimpleNamespace(YOLO=Mock()))
    return importlib.import_module('src.main')


def make_pipeline(module, tmp_path, monkeypatch, telemetry):
    from src.db.models import Base, Shift, Wagon
    path = tmp_path / 'pipeline.db'
    engine = create_engine(f'sqlite:///{path}')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add(Shift(id=1, operator_name='test'))
        db.add(Wagon(id=1, shift_id=1, wagon_number='001'))
        db.commit()
    monkeypatch.setattr(module, 'SessionLocal', sessions)
    p = module.BagCountingPipeline.__new__(module.BagCountingPipeline)
    p.telemetry = telemetry
    p.volume_est = module.VolumeEstimator(use_depth=False)
    p.tracker = module.BagTracker()
    p.tripwire = module.Tripwire(y_ratio=.75)
    p.handover = module.HandoverLogic()
    p.current_shift = SimpleNamespace(id=1)
    p.current_wagon = SimpleNamespace(id=1)
    p.clip_recorder = Mock()
    p.clip_recorder.save_clip.return_value = 'expected-evidence.mp4'
    return p, path, engine


def test_synthetic_replay_preserves_counts_and_dashboard(pipeline_module, tmp_path, monkeypatch):
    m = pipeline_module
    from src.pipeline.detector import Detection
    results = []
    for enabled in (False, True):
        run = tmp_path / str(enabled)
        run.mkdir()
        telemetry = RuntimePublisher('unused', interval=0) if enabled else Mock()
        p, path, engine = make_pipeline(m, run, monkeypatch, telemetry)
        detections = [[Detection(np.array([400., y-75, 600., y+75]), .9, 0)]
                      for y in range(650, 1010, 12)] + [[] for _ in range(25)]
        p.detector = Mock()
        p.detector.predict.side_effect = detections
        frame = np.zeros((1000,1000,3), dtype=np.uint8)
        p.camera = Mock(last_frame_monotonic=time.monotonic())
        frame_number = [0]
        def read():
            frame_number[0] += 1
            if frame_number[0] > len(detections):
                p.running = False
                return False, None, 0
            return True, frame, time.time()+frame_number[0]/25
        p.camera.read.side_effect = read
        monkeypatch.setattr(m.settings, 'USE_GUI', False)
        monkeypatch.setattr(m.time, 'sleep', lambda _: None)
        p._run()
        facts = queries.snapshot(path)
        assert facts['totals']['total'] == 1
        assert len(facts['recent']['events']) == 1
        assert sum(b['count'] for b in facts['series']['buckets']) == 1
        results.append(facts['totals'])
        if enabled:
            assert telemetry.data['last_event_id'] == facts['recent']['events'][0]['id']
        engine.dispose()
    assert results[0] == results[1]


def test_failed_commit_does_not_emit_saved_event(pipeline_module, tmp_path, monkeypatch):
    m = pipeline_module
    telemetry = RuntimePublisher('unused')
    p, path, engine = make_pipeline(m, tmp_path, monkeypatch, telemetry)
    db = Mock()
    db.commit.side_effect = RuntimeError('simulated database lock')
    monkeypatch.setattr(m, 'SessionLocal', lambda: db)
    track = m.Track(id=1, bbox=np.array([0,0,10,10]), volume_liters=10)
    p._count_bag(track)
    assert 'last_event_id' not in telemetry.data
    assert telemetry.data['alerts'][0]['code'] == 'persistence'
    assert queries.snapshot(path)['totals']['total'] == 0
    # Existing production behavior is characterized, not repaired in this change.
    assert track.counted
    db.rollback.assert_called_once()
    engine.dispose()


def test_shutdown_releases_capture_before_waiting_for_telemetry(pipeline_module, monkeypatch):
    import threading
    entered, release = threading.Event(), threading.Event()
    client = Mock()
    def execute():
        entered.set()
        release.wait(2)
    client.pipeline.return_value.execute.side_effect = execute
    telemetry = RuntimePublisher('unused', client=client)
    telemetry.start()
    assert entered.wait(1)
    pipeline = pipeline_module.BagCountingPipeline.__new__(pipeline_module.BagCountingPipeline)
    pipeline.telemetry = telemetry
    pipeline.camera = Mock()
    pipeline.camera.stop.side_effect = release.set
    pipeline.clip_recorder = Mock()
    monkeypatch.setattr(pipeline_module.cv2, 'destroyAllWindows', lambda: None)
    started = time.monotonic()
    pipeline.shutdown()
    assert time.monotonic() - started < .5
    assert not telemetry.thread.is_alive()
    pipeline.clip_recorder.shutdown.assert_called_once()
