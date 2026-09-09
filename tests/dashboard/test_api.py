import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends
from jose import jwt
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.config import settings
from src.dashboard import api
from tests.dashboard.test_queries import database


@pytest.fixture
def client(database, monkeypatch):
    monkeypatch.setattr(settings, 'DB_PATH', database)
    monkeypatch.setattr(settings, 'API_SECRET_KEY', 'test-secret-only-at-least-32-characters')
    monkeypatch.setattr(settings, 'API_ADMIN_USER', 'operator')
    monkeypatch.setattr(settings, 'API_ADMIN_PASS', 'test-password')
    async def unavailable():
        return {'status': {'state':'unavailable'}, 'data': None}
    monkeypatch.setattr(api, 'runtime', unavailable)
    oauth = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login', auto_error=False)
    def user(token=Depends(oauth)):
        try:
            return jwt.decode(token, settings.API_SECRET_KEY, algorithms=['HS256'])['sub']
        except Exception:
            return None
    app = FastAPI()
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(api.create_router(user, limiter))
    with TestClient(app) as c:
        yield c


def test_snapshot_and_query_validation(client):
    assert client.get('/api/v1/dashboard/snapshot').json()['totals']['total'] == 2
    assert client.get('/api/v1/events', params={'car_id':1, 'limit':101}).status_code == 422
    assert client.get('/api/v1/counts/timeseries', params={'car_id':1, 'from':'2026-01-01T00:00:00', 'to':'2026-01-01T01:00:00'}).status_code == 422
    assert client.get('/api/v1/counts/timeseries', params={'car_id':1, 'from':'2026-01-01T00:00:00Z', 'to':'2026-01-03T01:00:00Z'}).status_code == 422


def test_login_edit_and_conflict(client):
    assert client.patch('/api/v1/wagons/1', json={'number':'001','revision':0}).status_code == 401
    assert client.post('/api/v1/auth/login', data={'username':'bad','password':'bad'}).status_code == 401
    token = client.post('/api/v1/auth/login', data={'username':'operator','password':'test-password'}).json()['access_token']
    headers = {'Authorization':'Bearer '+token}
    assert client.patch('/api/v1/wagons/1', json={'number':'  ','revision':0}, headers=headers).status_code == 422
    assert client.patch('/api/v1/wagons/1', json={'number':'x'*33,'revision':0}, headers=headers).status_code == 422
    response = client.patch('/api/v1/wagons/1', json={'number':' 00123456 ','revision':0}, headers=headers)
    assert response.json()['number'] == '00123456'
    assert client.patch('/api/v1/wagons/1', json={'number':'00123456','revision':0}, headers=headers).status_code == 409
    expired = jwt.encode({'sub':'operator','exp':1}, settings.API_SECRET_KEY, algorithm='HS256')
    assert client.patch('/api/v1/wagons/1', json={'number':'001','revision':1}, headers={'Authorization':'Bearer '+expired}).status_code == 401


def test_login_rate_limit(client):
    for _ in range(5):
        assert client.post('/api/v1/auth/login', data={'username':'bad','password':'bad'}).status_code == 401
    assert client.post('/api/v1/auth/login', data={'username':'bad','password':'bad'}).status_code == 429


def test_snapshot_race_is_reconciled_after_subscribing(client, database, monkeypatch):
    import sqlite3
    import fakeredis
    import fakeredis.aioredis
    from src.dashboard.telemetry import channel
    server = fakeredis.FakeServer()
    monkeypatch.setattr(api, 'redis_client', lambda: fakeredis.aioredis.FakeRedis(server=server))
    original = api.full_snapshot
    first = True
    async def racing_snapshot():
        nonlocal first
        result = await original()
        if first:
            first = False
            with sqlite3.connect(database) as db:
                db.execute("INSERT INTO bag_events VALUES(5,1,'CLASS_25KG',datetime('now'),NULL)")
            publisher = fakeredis.aioredis.FakeRedis(server=server)
            await publisher.publish(channel(settings.DASHBOARD_SOURCE_ID), 'committed-during-snapshot')
            await publisher.aclose()
        return result
    monkeypatch.setattr(api, 'full_snapshot', racing_snapshot)
    with client.websocket_connect('/api/v1/dashboard/live') as socket:
        initial = socket.receive_json()
        repaired = socket.receive_json()
        assert initial['data']['totals']['total'] == 2
        assert repaired['data']['totals']['total'] == 3
        assert repaired['sequence'] > initial['sequence']
        assert len(repaired['data']['recent']['events']) == 3
