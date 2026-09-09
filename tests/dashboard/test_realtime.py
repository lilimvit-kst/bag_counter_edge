"""Real Redis/API/browser recovery, isolated from production storage and cameras."""
import asyncio
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from types import SimpleNamespace

import fakeredis.aioredis
import numpy as np
import pytest
import redis
import requests
from playwright.sync_api import expect
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.dashboard import api
from src.dashboard.telemetry import RuntimePublisher, channel
from tests.dashboard.test_browser import browser
from tests.dashboard.test_queries import database
from tests.dashboard.test_pipeline import pipeline_module
from tests.dashboard.test_deployment import credential_environment


@pytest.fixture
def services(database, tmp_path):
    binary = os.environ.get('DASHBOARD_TEST_REDIS_SERVER') or shutil.which('redis-server')
    if not binary:
        pytest.skip('Set DASHBOARD_TEST_REDIS_SERVER to run real restart acceptance')
    root = Path(__file__).resolve().parents[2]
    redis_url = f'unix://{tmp_path}/redis.sock'
    client = redis.Redis.from_url(redis_url, socket_timeout=.5)
    with socket.socket() as reserve:
        reserve.bind(('127.0.0.1', 0))
        port = reserve.getsockname()[1]
    origin = f'http://127.0.0.1:{port}'
    deployed = credential_environment('docker-compose.yml', {
        'ADMIN_USERNAME':'operator', 'ADMIN_PASSWORD':'test-password'})
    env = dict(os.environ, DB_PATH=str(database), PYTHONPATH=str(root), REDIS_URL=redis_url,
               API_SECRET_KEY='test-only-secret-at-least-32-characters', **deployed)
    processes = {}

    def start(role):
        command = ([binary, '--port', '0', '--unixsocket', str(tmp_path/'redis.sock'),
                    '--save', '', '--appendonly', 'no'] if role == 'redis' else
                   [sys.executable, '-m', 'uvicorn', 'tests.dashboard.server:app',
                    '--host', '127.0.0.1', '--port', str(port), '--log-level', 'error'])
        processes[role] = subprocess.Popen(command, cwd=tmp_path, env=env,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                ready = client.ping() if role == 'redis' else requests.get(origin+'/api/v1/dashboard/snapshot', timeout=.5).ok
                if ready:
                    return
            except (redis.RedisError, requests.RequestException):
                pass
            assert processes[role].poll() is None, f'{role} exited at startup'
            time.sleep(.05)
        pytest.fail(f'{role} did not start')

    def stop(role):
        process = processes.pop(role)
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

    try:
        start('redis')
        start('api')
        yield origin, redis_url, client, start, stop
    finally:
        for role in list(processes):
            stop(role)
        client.close()


def test_browser_recovers_from_real_restarts_and_missed_counts(browser, services, database, pipeline_module, monkeypatch):
    origin, redis_url, client, start, stop = services
    publisher = RuntimePublisher(redis_url)
    publisher.start(time.monotonic)
    publisher.update(state='running')
    context = browser.new_context(locale='en-GB')
    page = context.new_page()
    messages = []
    page.on('websocket', lambda socket: socket.on('framereceived', lambda message: messages.append(message)))
    try:
        page.goto(origin)
        expect(page.locator('#count')).to_have_text('2')
        expect(page.locator('#status')).to_have_text('Online')
        # One unconfirmed candidate between publication ticks survives later
        # empty frames all the way through real Redis/API/browser delivery.
        captured = time.time()
        frame = np.zeros((100,100,3), dtype=np.uint8)
        publisher.observe(frame, [], [], captured)
        publisher.observe(frame, [SimpleNamespace(confidence=.9, bbox=[10,10,50,50])], [], captured+.1)
        publisher.observe(frame, [], [], captured+.6)
        expect(page.locator('#detection-state')).to_have_text('Unconfirmed', timeout=8000)
        expect(page.locator('#detection-class')).to_have_text('Unknown')
        expect(page.locator('#thumbnail')).to_be_visible()
        expect(page.locator('#count')).to_have_text('2')
        page.wait_for_timeout(600)
        assert messages, 'Acceptance must exercise live WebSocket delivery as well as polling'
        publisher.close()
        expect(page.locator('#status')).to_have_text('Offline', timeout=8000)

        # A different CV run replaces the stopped run without incrementing totals.
        previous_run = publisher.data['run_id']
        publisher = RuntimePublisher(redis_url)
        publisher.start(time.monotonic)
        publisher.update(state='running')
        assert publisher.data['run_id'] != previous_run
        expect(page.locator('#status')).to_have_text('Online', timeout=8000)
        expect(page.locator('#detection-class')).to_have_text('No detection yet')

        stop('redis')
        expect(page.locator('#status')).to_have_text('Status unavailable', timeout=8000)
        bridge = page.locator('[data-incident="communication:redis"]')
        expect(bridge).to_contain_text('Active')
        expect(bridge).to_contain_text('First ')
        expect(bridge).to_contain_text('Last ')
        expect(page.locator('#count')).to_have_text('2')
        # Persist without any notification, then recover the bridge.
        with sqlite3.connect(database) as db:
            db.execute("INSERT INTO bag_events VALUES(5,1,'CLASS_25KG',datetime('now'),NULL)")
        expect(page.locator('#count')).to_have_text('3', timeout=8000)
        expect(bridge).to_contain_text('Active')  # HTTP/WS still work during Redis loss
        start('redis')
        publisher.completed('detector')
        publisher.completed('tracker')
        expect(page.locator('#status')).to_have_text('Online', timeout=8000)
        expect(bridge).to_contain_text('Recovered')
        for _ in range(100):
            client.publish(channel('primary'), 'duplicate-notification')
        expect(page.locator('#count')).to_have_text('3')

        # A real API process restart repairs the same browser document.
        page.evaluate('window.originalDocument = document.documentElement')
        stop('api')
        expect(page.locator('[data-incident="communication:websocket"]')).to_contain_text('Active', timeout=8000)
        expect(page.locator('#status')).to_have_text('Status unavailable', timeout=18000)
        with sqlite3.connect(database) as db:
            db.execute("INSERT INTO bag_events VALUES(6,1,'CLASS_50KG',datetime('now'),NULL)")
        start('api')
        expect(page.locator('#count')).to_have_text('4', timeout=12000)
        expect(page.locator('[data-incident="communication:websocket"][data-active="true"]')).to_have_count(0, timeout=8000)
        expect(page.locator('[data-incident="communication:http"][data-active="true"]')).to_have_count(0, timeout=8000)
        page.locator('#show-alerts').click()
        expect(bridge).to_contain_text('Recovered')
        expect(page.locator('[data-incident="communication:websocket"]').last).to_contain_text('Recovered')
        page.locator('#alerts-dialog .close-dialog').click()
        assert page.evaluate('window.originalDocument === document.documentElement')
        expect(page.locator('#events tr')).to_have_count(4)

        # Exercise the actual login/PATCH routes and revision conflict.
        page.locator('#edit-car').click()
        page.locator('#car-input').fill('00123456')
        page.locator('#username').fill('operator')
        page.locator('#password').fill('test-password')
        with sqlite3.connect(database) as db:
            db.execute('UPDATE wagons SET revision=revision+1 WHERE id=1')
        page.locator('#save-car').click()
        expect(page.locator('#car-error')).to_contain_text('Car information changed')
        page.locator('#save-car').click()
        expect(page.locator('#car-number')).to_have_text('00123456')
        expect(page.locator('#count')).to_have_text('4')
        assert requests.get(origin+'/api/v1/dashboard/snapshot', timeout=2).json()['car']['id'] == 1

        # Inject a commit failure through the real counting method and observe it
        # across Redis, the API and the browser without adding a durable count.
        pipeline = pipeline_module.BagCountingPipeline.__new__(pipeline_module.BagCountingPipeline)
        pipeline.telemetry = publisher
        pipeline.volume_est = pipeline_module.VolumeEstimator(use_depth=False)
        pipeline.current_shift = SimpleNamespace(id=4)
        pipeline.current_wagon = SimpleNamespace(id=1)
        pipeline.clip_recorder = Mock()
        session = Mock()
        session.commit.side_effect = sqlite3.OperationalError('injected write failure')
        monkeypatch.setattr(pipeline_module, 'SessionLocal', lambda: session)
        track = pipeline_module.Track(id=99, bbox=np.array([0,0,10,10]), volume_liters=10)
        pipeline._count_bag(track)
        publisher.completed('detector')
        publisher.completed('tracker')
        session.rollback.assert_called_once()
        expect(page.locator('#alert-title')).to_have_text('A bag count could not be saved', timeout=8000)
        expect(page.locator('#count')).to_have_text('4')
        assert 'last_event_id' not in publisher.data
    finally:
        publisher.close()
        context.close()


@pytest.mark.asyncio
async def test_slow_client_is_disconnected_and_releases_subscription(monkeypatch):
    client = fakeredis.aioredis.FakeRedis()
    closed = AsyncMock(wraps=client.aclose)
    monkeypatch.setattr(client, 'aclose', closed)
    monkeypatch.setattr(api, 'redis_client', lambda: client)
    monkeypatch.setattr(api, 'full_snapshot', AsyncMock(return_value={'totals': {'total': 7}}))
    router = api.create_router(lambda: None, Limiter(key_func=get_remote_address))
    endpoint = next(route.endpoint for route in router.routes if route.path.endswith('/dashboard/live'))
    class SlowSocket:
        accept = AsyncMock()
        close = AsyncMock()
        async def receive(self):
            await asyncio.Future()
        async def send_json(self, message):
            await asyncio.Future()
    await asyncio.wait_for(endpoint(SlowSocket()), timeout=3)
    closed.assert_awaited_once()
    SlowSocket.close.assert_awaited_once_with(code=1001)
