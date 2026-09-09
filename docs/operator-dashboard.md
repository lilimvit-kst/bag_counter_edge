# Operator dashboard

The primary dashboard is a locally served browser application. It displays saved
bags for the single active car, class totals, a 30-minute graph, recent saved
events, the last detection, component status and grouped operational warnings.
The clock and timestamps follow the computer displaying the dashboard. Existing
SQLite timestamps without offsets are interpreted as UTC, matching the pipeline's
UTC writes. No CDN, external font, cloud service or browser ML runtime is required.

## Car number

Choose **Edit number**, log in using the configured operator account, enter the
number and save. Leading zeros are retained. This corrects the current car's
number; its ID and bag associations remain unchanged. It does not open another
car or transfer bags. Concurrent edits return a conflict and preserve typed text.
If no unique active car exists, the dashboard shows a context warning.

Use `API_ADMIN_USER`, `API_ADMIN_PASS` and `API_SECRET_KEY` for the configured
operator. All three Compose variants map legacy `ADMIN_USERNAME`/`ADMIN_PASSWORD`
inputs to `API_ADMIN_USER`/`API_ADMIN_PASS`. Nonempty canonical values take
precedence; empty or unset canonical values fall back to the legacy inputs, then
to the existing Compose defaults (`admin`/`changeme`). Direct application startup
uses the canonical names; unrelated legacy Settings aliases remain unchanged.
Configure credentials through deployment secrets/environment without committing them.
Read APIs retain their existing access policy. Car edits require an expiring
operator JWT held only in browser memory. Reloading the page requires login again
for edits. Use HTTPS through the deployment proxy outside a trusted kiosk network.

## Status meaning

- **Online:** counting model initialized and service progressing; an empty conveyor
  is normal and shows Waiting for bags.
- **Starting:** model initialization is in progress.
- **Offline:** model stopped, failed, stopped reporting or processing stalled.
- **Online / Counting interrupted:** service alive but camera frames unavailable.
- **Status unavailable:** communication failure prevents a current conclusion.

Camera status uses actual capture freshness. The optional MJPEG preview opens a
separate camera connection and does not establish counting health. A detection is
not a saved count. Totals, graph and recent counts come from committed database
events. Existing counting and persistence defects documented in BASELINE_AUDIT.md
are not repaired by this dashboard change.

The last selected observation is retained immediately, even if visible for less
than 500 ms. Subsequent empty frames retain its time and class; only a newer
observation replaces it. Candidates without a confirmed track show **Unconfirmed**,
separately from **Unknown** classification. Thumbnail candidates are bounded to
192 pixels per side; images expire after 30 seconds while observation metadata
remains. A new counting-process run resets its detection state.

Warning details retain up to **20 incident episodes for the current page session**,
including communication failures, derived status warnings and grouped runtime
faults. Each entry shows severity, source, first/last occurrence, count and recovery
time. Repeated active reports coalesce; a subsequent outage starts another episode.
The oldest recovered episode is removed first when full. A healthy summary may
say **No active warnings** while the drawer still shows recovered incidents.
History survives snapshots and counting-process restarts; reloading the page
clears it. It is not a durable alarm log. HTTP, WebSocket and Redis failures recover
independently. A broken WebSocket with fresh HTTP data does not change an Online
counting model to Offline; after 12 seconds without a fresh snapshot, its status
becomes unavailable and saved values remain visible.

## Runtime settings

| Setting | Default | Meaning |
|---|---:|---|
| `DASHBOARD_SOURCE_ID` | `primary` | Shared source identifier in API and CV processes |
| `DASHBOARD_TELEMETRY_TTL` | `5` | Seconds before missing runtime publication expires |
| `DASHBOARD_CAMERA_TIMEOUT` | `5` | Maximum fresh-frame age in seconds |
| `DASHBOARD_PROCESSING_TIMEOUT` | `15` | Maximum detector/tracker completion age in seconds |
| `REDIS_URL` | Existing deployment setting | Transient shared runtime state and notifications |

The default heartbeat/publication interval is **0.5 seconds**, at most twice per
second, with a 5-second expiry. Observation capture is immediate and is not
throttled by that interval; only publication/render updates are coalesced. Redis
network operations and thumbnail encoding run on a separate worker with bounded
socket timeouts and shutdown wait. API snapshots reconcile database facts at least
every five seconds during normal connectivity. WebSocket clients receive full
replacement snapshots, never increment instructions. Browser fallback polling
recovers from missed notifications. Redis loss cannot block the counting loop.
Check processing deadlines on the target CPU with its actual model before rollout.

## Additive API routes

Existing API routes, task inputs, legacy WebSocket messages and MJPEG contracts
remain supported. Dashboard additions:

- `GET /api/v1/dashboard/snapshot`
- `GET /api/v1/events?car_id=1&limit=6&before=123` (limit 1–100, cursor optional)
- `GET /api/v1/counts/timeseries?car_id=1&from=...&to=...` (offset-qualified
  timestamps, half-open interval, maximum 24 hours)
- `POST /api/v1/auth/login` (OAuth2 form username/password)
- `PATCH /api/v1/wagons/{id}` (JSON number/revision with bearer token)
- `WebSocket /api/v1/dashboard/live`

`/api/v1/stats/today` is retained as-is for legacy clients. The new dashboard uses
its own car-scoped queries. API errors use operator-safe messages. Detailed
diagnostics remain in service logs and maintenance tools.
Time-series bounds and minute buckets preserve stored microsecond precision after
UTC normalization. For example, `10:00:59.999999` is included in `[10:00,10:01)`;
an event exactly at `10:01` is excluded. The read streams the selected car's
timestamp index to accommodate both naive UTC and offset-qualified stored values
without rewriting events; query cost grows with that car's saved event history.

## Deployment and migration

Use the existing Compose stack and storage/model mounts. The dashboard service
now builds `Dockerfile.operator` and serves static assets on port 80 internally.
nginx serves the UI at `/`, proxies `/api/` including live updates/video, and
preserves `/ws/` for legacy API clients. Worker and beat entrypoint dispatch honors
their commands and does not start CV processes.

Before updating a populated installation, stop application writers and make a
verified SQLite backup. Run the explicit additive migration with services stopped:

```bash
python -m src.db.dashboard_migration --db /absolute/path/to/storage/db/bag_counter.db
```

The migration adds `wagons.revision` and an event car/time index. It is rerunnable
and preserves event IDs, totals, ownership and evidence paths. It never creates a
database accidentally. For a new empty installation, initialize tables first with
the normal application initialization, or
`python -c 'from src.db.models import init_db; init_db()'`, then run the migration
before exposing the dashboard.

For container-based migration, build the new edge image and use:

```bash
docker compose run --rm --no-deps edge-cv python -m src.db.dashboard_migration --db /app/storage/db/bag_counter.db
```

Deploy the backend/telemetry before switching dashboard routing. Verify one CV
producer, working Celery worker/beat, login, manual number correction, graph,
video and browser reconnect. Do not run additional CV producers as a preview.

## Rollback and maintenance

Roll back the dashboard route and compatible API image first. Retain additive
columns/indexes and corrected car numbers. Never restore an old database backup
over new count events. The former `Dockerfile.dashboard` and Streamlit source
remain available for an explicitly started maintenance instance; they are not the
primary Compose dashboard. To temporarily route to that instance, use its original
8501 upstream. Do not use its car/shift switching actions during active loading:
the existing CV process caches its startup car context. New loading-session
lifecycle operations require a separate change.

## Verification

Install application test dependencies plus `requirements-dashboard-test.txt` in an
isolated environment, then install the Playwright Chromium browser and required
system libraries. Install a local Redis server for the process-restart acceptance
test, or set `DASHBOARD_TEST_REDIS_SERVER` to its executable. That test starts its
own isolated Redis and API processes with temporary storage; it is skipped when
no Redis executable is available. Run:

```bash
python -m pytest tests/dashboard
python -m pytest tests/test_api.py tests/test_notifications.py
node --check frontend/app.js
openspec validate redesign-operator-dashboard --strict
openspec validate --all --strict
```

Browser fixtures serve local assets with deterministic responses and exercise desktop
fit at 1366×768, 1500×950, 1920×950 and 1920×1080 (including adjacent breakpoints),
timezone display, live updates, conflicts and unavailable preview. Credential tests
expand the actual Compose credential expressions with isolated environment inputs
and initialize Settings before exercising login/protected routes. These static
wiring tests do not substitute for built-container acceptance. Restart
acceptance also uses the real API, Redis and browser WebSocket, including injected
commit failure through the counting method, retained brief detections and timestamped
communication recovery history. Synthetic
pipeline tests use the actual tracker/tripwire/handover and temporary SQLite, with
inference outputs provided as fixtures. They do not measure model accuracy.

Before production acceptance, perform built-container process-role checks in task
8.2, manual camera/kiosk checks in 9.3 and target CPU/rollout checks in 9.5. An emulated browser cannot establish
physical camera recovery, actual monitor readability or edge inference latency.
