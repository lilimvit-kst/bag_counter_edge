"""Additive dashboard routes. Legacy routes and WebSocket messages are untouched."""
import asyncio
import hmac
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from pydantic import BaseModel, Field, field_validator

from src.config import settings
from src.dashboard import queries
from src.dashboard.telemetry import channel, derive_status, runtime_key


def redis_client():
    return redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=0.25, socket_timeout=0.5)


async def runtime():
    client = redis_client()
    try:
        pipe = client.pipeline(transaction=True)
        pipe.get(runtime_key(settings.DASHBOARD_SOURCE_ID))
        pipe.pttl(runtime_key(settings.DASHBOARD_SOURCE_ID))
        raw, remaining_ms = await pipe.execute()
        data = json.loads(raw) if raw else None
        if data:
            # Redis TTL measures residence age without depending on host wall-clock agreement.
            residence = max(0, data.get('ttl', settings.DASHBOARD_TELEMETRY_TTL) - remaining_ms / 1000)
            data['ages'] = {k: v + residence for k, v in data.get('ages', {}).items()}
            data['uptime'] = data.get('uptime', 0) + residence
            if data.get('camera_age') is not None:
                data['camera_age'] += residence
        status = derive_status(data, camera_deadline=settings.DASHBOARD_CAMERA_TIMEOUT,
                               stage_deadline=settings.DASHBOARD_PROCESSING_TIMEOUT)
        return {'status': status, 'data': data}
    except (redis.RedisError, ValueError, KeyError, TypeError):
        return {'status': derive_status(None, available=False), 'data': None}
    finally:
        await client.aclose()


def read_snapshot():
    try:
        return queries.snapshot(settings.DB_PATH.resolve())
    except sqlite3.Error:
        raise HTTPException(503, 'Saved counts are temporarily unavailable')


async def full_snapshot():
    facts, live = await asyncio.gather(asyncio.to_thread(read_snapshot), runtime())
    facts['runtime'] = live
    return facts


class CarEdit(BaseModel):
    number: str = Field(max_length=128)
    revision: int = Field(ge=0)

    @field_validator('number')
    @classmethod
    def clean_number(cls, value):
        value = value.strip()
        if not 1 <= len(value) <= 32 or any(ord(c) < 32 for c in value):
            raise ValueError('Enter a car number of 1 to 32 characters')
        return value


def create_router(current_user, limiter):
    router = APIRouter(prefix='/api/v1')

    @router.post('/auth/login')
    @limiter.limit('5/minute')
    async def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
        valid_user = hmac.compare_digest(form.username.encode(), settings.API_ADMIN_USER.encode())
        valid_pass = hmac.compare_digest(form.password.encode(), settings.API_ADMIN_PASS.encode())
        if not (valid_user and valid_pass):
            raise HTTPException(401, 'Invalid operator credentials')
        expires = datetime.now(timezone.utc) + timedelta(minutes=settings.API_TOKEN_EXPIRE_MINUTES)
        token = jwt.encode({'sub': settings.API_ADMIN_USER, 'exp': expires}, settings.API_SECRET_KEY, algorithm='HS256')
        return {'access_token': token, 'token_type': 'bearer', 'expires_at': expires.isoformat()}

    @router.get('/dashboard/snapshot')
    async def dashboard_snapshot():
        return await full_snapshot()

    @router.get('/events')
    def events(car_id: int = Query(gt=0), limit: int = Query(6, ge=1, le=100), before: int | None = Query(None, gt=0)):
        try:
            with queries.connection(settings.DB_PATH.resolve()) as db:
                return queries.history(db, car_id, limit, before)
        except sqlite3.Error:
            raise HTTPException(503, 'Saved events are temporarily unavailable')

    @router.get('/counts/timeseries')
    def counts(car_id: int = Query(gt=0), start: datetime = Query(alias='from'), end: datetime = Query(alias='to')):
        if start.tzinfo is None or end.tzinfo is None or not timedelta(0) < end-start <= timedelta(hours=24):
            raise HTTPException(422, 'Use timezone-qualified bounds spanning at most 24 hours')
        try:
            with queries.connection(settings.DB_PATH.resolve()) as db:
                return queries.series(db, car_id, start, end)
        except sqlite3.Error:
            raise HTTPException(503, 'Count history is temporarily unavailable')

    @router.patch('/wagons/{car_id}')
    def edit_car(car_id: int, edit: CarEdit, user=Depends(current_user)):
        if not user or user != settings.API_ADMIN_USER:
            raise HTTPException(401, 'Operator login required')
        try:
            return queries.correct_car(settings.DB_PATH.resolve(), car_id, edit.number, edit.revision)
        except queries.CarConflict as exc:
            raise HTTPException(409, {'message': 'Car information changed. Review the current number and try again.', 'current': exc.current})
        except sqlite3.Error:
            raise HTTPException(503, 'Car number could not be saved. Try again.')
        # Periodic snapshots reconcile edits even if no live notification is available.

    @router.websocket('/dashboard/live')
    async def live(websocket: WebSocket):
        await websocket.accept()
        client = redis_client()
        pubsub = client.pubsub()
        sequence = 0
        changed = asyncio.Event()

        async def wait_disconnect():
            while True:
                message = await websocket.receive()
                if message['type'] == 'websocket.disconnect':
                    return
        async def watch_changes():
            # Drain notifications independently of slow snapshots/clients. One bit
            # coalesces all pending invalidations; no notification queue accumulates.
            while True:
                try:
                    await pubsub.subscribe(channel(settings.DASHBOARD_SOURCE_ID))
                    while True:
                        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
                        if message:
                            changed.set()
                except redis.RedisError:
                    changed.set()
                    await asyncio.sleep(1)

        disconnect = asyncio.create_task(wait_disconnect())
        watcher = None
        try:
            # Subscribe before initial DB read: queued invalidations repair snapshot races.
            try:
                await pubsub.subscribe(channel(settings.DASHBOARD_SOURCE_ID))
            except redis.RedisError:
                pass
            watcher = asyncio.create_task(watch_changes())
            while not disconnect.done():
                sequence += 1
                try:
                    data = await full_snapshot()
                    envelope = {'type': 'snapshot', 'sequence': sequence, 'data': data}
                except HTTPException:
                    envelope = {'type': 'error', 'sequence': sequence, 'message': 'Saved counts are temporarily unavailable'}
                # At most one snapshot in flight per client; no shared lock or unbounded queue.
                await asyncio.wait_for(websocket.send_json(envelope), timeout=2)
                await asyncio.sleep(0.5)
                try:
                    await asyncio.wait_for(changed.wait(), timeout=4.5)
                except asyncio.TimeoutError:
                    pass
                changed.clear()
        except (WebSocketDisconnect, RuntimeError, asyncio.TimeoutError, OSError):
            pass
        finally:
            disconnect.cancel()
            if watcher:
                watcher.cancel()
            await asyncio.gather(disconnect, *([watcher] if watcher else []), return_exceptions=True)
            await pubsub.aclose()
            await client.aclose()
            try:
                await asyncio.wait_for(websocket.close(code=1001), timeout=0.25)
            except (RuntimeError, OSError, asyncio.TimeoutError):
                pass

    return router
