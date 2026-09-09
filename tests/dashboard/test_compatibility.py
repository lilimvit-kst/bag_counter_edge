"""Existing interfaces retain their behavior alongside dashboard additions."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api import app as legacy
from src.config import settings
from src.db.models import Base, BagEvent, BagClass, Shift, Wagon
from tests.dashboard.test_deployment import COMPOSE_FILES, credential_environment


@pytest.mark.parametrize('compose', COMPOSE_FILES)
@pytest.mark.parametrize('mode', ['legacy', 'canonical', 'conflicting'])
def test_deployment_environment_authentication(compose, mode, monkeypatch):
    from src.config import Settings
    from src.dashboard import api
    from src.tasks import tasks
    inputs = {}
    if mode in ('legacy', 'conflicting'):
        inputs.update(ADMIN_USERNAME='legacy-operator', ADMIN_PASSWORD='legacy-test-password')
    if mode in ('canonical', 'conflicting'):
        inputs.update(API_ADMIN_USER='canonical-operator', API_ADMIN_PASS='canonical-test-password')
    deployed = credential_environment(compose, inputs)
    for key in ('ADMIN_USERNAME', 'ADMIN_PASSWORD', 'API_ADMIN_USER', 'API_ADMIN_PASS'):
        monkeypatch.delenv(key, raising=False)
    for key, value in deployed.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv('API_SECRET_KEY', 'deployment-test-only-at-least-32-characters')
    configured = Settings(_env_file=None)
    monkeypatch.setattr(api, 'settings', configured)
    monkeypatch.setattr(legacy, 'settings', configured)
    legacy.slowapi_limiter.reset()
    delay = Mock(return_value=Mock(id='configured-task'))
    monkeypatch.setattr(tasks.send_notification_task, 'delay', delay)
    prefix = 'legacy' if mode == 'legacy' else 'canonical'
    with TestClient(legacy.app) as client:
        assert client.post('/api/v1/auth/login', data={'username':prefix+'-operator', 'password':'wrong'}).status_code == 401
        if mode == 'conflicting':
            assert client.post('/api/v1/auth/login', data={'username':'legacy-operator', 'password':'legacy-test-password'}).status_code == 401
        token = client.post('/api/v1/auth/login', data={
            'username':prefix+'-operator', 'password':prefix+'-test-password'}).json()['access_token']
        response = client.post('/api/v1/tasks/send-notification', json={'event_type':'test', 'data':{}},
                               headers={'Authorization':'Bearer '+token})
        assert response.json() == {'task_id':'configured-task', 'status':'queued'}
        delay.assert_called_once()


def test_legacy_read_and_protected_task_contracts(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path}/legacy.db')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add(Shift(id=1, operator_name='Test'))
        db.add(Wagon(id=1, shift_id=1, wagon_number='001'))
        db.add(BagEvent(id=1, wagon_id=1, shift_id=1, track_id=1, bag_class=BagClass.CLASS_25KG))
        db.commit()
    def database():
        with sessions() as db:
            yield db
    monkeypatch.setattr(settings, 'API_ADMIN_USER', 'operator')
    monkeypatch.setattr(settings, 'API_ADMIN_PASS', 'test-password')
    monkeypatch.setattr(settings, 'API_SECRET_KEY', 'test-only-at-least-32-character-secret')
    legacy.app.dependency_overrides[legacy.get_db] = database
    from src.tasks import tasks
    delay = Mock(return_value=Mock(id='legacy-task-id'))
    monkeypatch.setattr(tasks.send_notification_task, 'delay', delay)
    try:
        with TestClient(legacy.app) as client:
            # Preserve the established all-event statistic (even uncounted rows).
            assert set(client.get('/api/v1/wagons/active').json()) == {'id','number','started_at'}
            assert client.get('/api/v1/stats/today').json() == {
                'total_counted':1, 'by_class':{'25kg':1,'50kg':0,'empty':0}}
            body = {'event_type':'test','data':{}}
            assert client.post('/api/v1/tasks/send-notification', json=body).status_code == 401
            token = client.post('/api/v1/auth/login', data={
                'username':'operator','password':'test-password'}).json()['access_token']
            reply = client.post('/api/v1/tasks/send-notification', json=body,
                                headers={'Authorization':'Bearer '+token})
            assert reply.json() == {'task_id':'legacy-task-id','status':'queued'}
            delay.assert_called_once()
    finally:
        legacy.app.dependency_overrides.clear()
        engine.dispose()


def test_legacy_websocket_messages():
    with TestClient(legacy.app) as client:
        with client.websocket_connect('/ws/dashboard') as socket:
            manager = legacy.get_ws_manager()
            for method, kind in [(manager.broadcast_stats, 'stats_update'),
                                 (manager.broadcast_event, 'bag_detected'),
                                 (manager.broadcast_alert, 'alert')]:
                # General subscribers retain the existing all-channel contract.
                client.portal.call(manager.subscribe, next(iter(manager.active_connections)), 'general')
                client.portal.call(method, {'total':4})
                message = socket.receive_json()
                assert message['type'] == kind and message['data'] == {'total':4}
                assert 'timestamp' in message


@pytest.mark.asyncio
async def test_legacy_mjpeg_headers_and_placeholder(monkeypatch):
    camera = Mock()
    camera.read.return_value = (False, None, 0)
    monkeypatch.setattr(legacy, 'get_camera_stream', lambda: camera)
    response = await legacy.video_stream()
    assert response.media_type == 'multipart/x-mixed-replace; boundary=frame'
    assert response.headers['cache-control'] == 'no-cache'
    frame = await anext(response.body_iterator)
    assert frame.startswith(b'--frame\r\nContent-Type: image/jpeg\r\n\r\n\xff\xd8')
    await response.body_iterator.aclose()
