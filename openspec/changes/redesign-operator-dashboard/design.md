## Context

See proposal.md for motivation. At the audited baseline, src/kiosk/dashboard.py reruns after 0.1 seconds, initializes ws_connected to false without updating it, never starts its WebSocketClient, uses fixed UTC+5 and directly mutates a cached database session. Its car form is nested inside a transient button branch. FastAPI and CV run in different processes; the in-memory WebSocket manager cannot bridge them. Baseline nginx has no API /ws route. The preview opens a separate camera connection. update_dashboard_task returns statistics but does not broadcast them. Baseline main Compose worker/beat commands are ignored by the shared entrypoint.

The user confirmed one car is filled at a time and bags are not transferred between cars. This change implements entering/correcting that car's display number. It does not add a new car-switching or in-flight transfer workflow. Existing startup context creation remains in place; later loading-session lifecycle work must explicitly resolve the cached pipeline context defect before exposing switching in the replacement UI.

## Goals / Non-Goals

**Goals:** A stable browser screen, trustworthy observable pipeline state, durable count-derived history, and safe manual number correction with one local origin.

**Non-Goals:** Model/tracker migration, new camera handover, count-rule changes, physical-bag exactly-once repair, clip extraction repair, or new shift/car lifecycle operations. Read-only instrumentation must preserve detector filtering, CPU execution, volume classification and tripwire/handover thresholds.

## Decisions

### Compatibility boundary

The operator monitoring screen is the primary product surface. Retain the existing backend architecture and HTTP routes, request/response shapes, authentication behavior and legacy WebSocket message types. Add dashboard-specific routes and envelopes rather than changing existing consumers. In particular, do not repurpose /api/v1/stats/today or change its historical behavior in this change; the new scoped queries supply correct dashboard data independently. Preserve the current MJPEG contract and existing task submission interfaces.

Backend additions are justified only by a dashboard requirement: snapshots/history for the count and graph; nonblocking telemetry for truthful camera/detector/tracker status and alerts; process bridging for live updates; login and optimistic number correction for manual car entry. Additive schema changes support that correction and bounded historical queries. Service-role correction prevents duplicate producers from corrupting the displayed loading state. Any further backend change requires an explicit scope revision. Compatibility tests must cover existing routes and WebSocket messages, not merely the new interface.

### 1. Dedicated browser UI with locally served assets

Use HTML/CSS and modular browser JavaScript under a new frontend directory, served by a lightweight dashboard container. Use CSS grid and a small SVG time-series chart; no runtime CDN, font dependency or frontend ML packages. This screen does not require a large application framework. Retaining Streamlit would reduce initial work but retain rerun and browser-state complexity; use it only as an opt-in maintenance fallback.

Header: fixed Bag Counter title, counting badge, car number/edit action and browser-local clock. Main grid: dominant saved count with class totals; compact component state and last-detection card; graph and expandable video; six recent events and alert summary. History/details use a drawer. Fit 1366x768, 1500x950, 1920x950 and 1920x1080 CSS pixels at normal zoom, with natural scrolling at smaller sizes. Size the enlarged layout against available viewport height, including header, gaps, alerts and footer; a breakpoint must not introduce vertical scrolling. Preserve the readable large count, preview, graph and six visible recent events at 1920x1080. Test immediately around the affected width/height breakpoint, including 1499/1500-pixel widths and 949/950/951-pixel heights, rather than only the two original endpoints. Do not hide required information or suppress document overflow to satisfy the fit check. Use text and icons as well as status colors. Keep keyboard focus and unsaved form state outside snapshot replacement. No raw paths, API URLs, confidence tuning, or maintenance links in the overview.

### 2. Separate persisted facts from expiring runtime observations

SQLite remains the source for count totals and event history. Add a dashboard service module to FastAPI that reads totals and recent events in one read transaction. API responses distinguish database snapshot time from telemetry freshness. Serialize existing naive SQLite timestamps as UTC according to this repository's UTC-writing convention; test legacy fixtures and document the assumption. Browser Date/Intl formatting uses the viewing computer timezone; interval queries are UTC half-open ranges [from,to).

Time-series filtering and bucket assignment must preserve stored microsecond precision after UTC normalization. Replace rounded julianday comparisons with an exact read-side UTC comparison or integer UTC-microsecond representation; do not introduce floating-point timestamp rounding. Treat naive stored values as UTC and offset-qualified values as the equivalent UTC instant. Any SQL prefilter must be conservative so it cannot discard a valid boundary event. Keep existing timestamps, event IDs, schema, query bounds, pagination and response shapes; this correction does not require rewriting events. Verify one microsecond before, exactly at, and one microsecond after both interval boundaries, including legacy naive and offset-qualified values. In particular, 10:00:59.999999 belongs to [10:00,10:01).

Instrument capture success, model initialization, inference completion, tracker completion, last detection and successful BagEvent commit. Capture health must use last successful acquisition, never repeated cached read success. Camera frames still flow through the unchanged YOLO -> tracker -> volume -> crossing -> handover -> persistence path. Counting telemetry is emitted only after db.commit succeeds; failures produce operational warnings without altering existing count retry semantics.

A bounded latest-state slot feeds a telemetry worker; never perform Redis calls on the critical frame-processing thread. Retain each selected detection observation immediately, replacing only an older observation. Coalesce publication/render work at the telemetry cadence, emit at most two state updates per second, use short network timeouts and recover the latest retained state after reconnection. Empty frames and publication backpressure must not erase a retained detection. Shutdown stops the worker with bounded waiting; pending telemetry does not delay camera/clip shutdown. Raw frames are not queued unboundedly.

### 3. Cross-process runtime bridge and explicit status semantics

Use existing Redis for expiring snapshots and change notifications keyed by source ID and process-run UUID. A process heartbeat and stage-completion timestamps are separate. Default heartbeat/publication interval is 0.5 seconds, permitting at most two publications per second, with a 5-second expiry; default processing stall deadline is 15 seconds, configurable and checked against actual edge inference latency before deployment. The 0.5-second default matches the implemented cadence and must agree across the guide, specifications and tests. It is not an observation-capture interval. An independent heartbeat must not conceal a stuck inference stage. Use local monotonic intervals inside a process; API receive time/Redis expiry governs cross-process freshness.

Online means initialized counting service with fresh liveness and expected progress. No bags is Online. Startup is Starting; explicit shutdown/fault or expired service liveness is Offline. A live service with unavailable frames remains Online with Camera unavailable and Counting interrupted, distinguishing runtime existence from effective counting. Healthy frames plus expired inference/tracker progress is Offline with stalled-stage reason. API-to-Redis failure is status unavailable, not proof the model stopped. Browser-to-API failure marks the entire displayed snapshot stale.

Group alerts by source and code, storing first/last occurrence, count, severity and active/recovered state in bounded runtime state. Full durable alert history is outside this change. Never publish credentials or raw camera URLs.

The browser also owns a bounded communication/derived-status incident history for the current page session, since an API or Redis outage cannot depend on publishing its own failure through the failed transport. Retain at most 20 incident episodes with source/code, first and last occurrence, occurrence count, severity, active/recovered state and recovery time. Coalesce repeated reports during one active episode; a later outage after recovery starts a new episode. Evict the oldest recovered episodes first when the bound is reached, and keep the active-state representation bounded. Preserve known incident context when a fresh snapshot arrives or a runtime run ID changes; do not rebuild this history solely from the latest snapshot. Process restarts still reset run-scoped detection/status data.

Keep failure and recovery signals specific to the dependency: successful fallback HTTP polling does not prove that a failed WebSocket or Redis connection recovered. Merge runtime warnings and communication/derived-status incidents in the details drawer without duplicate ongoing incidents. The overview may say No active warnings after recovery, but details must retain timestamped recovered incidents within the bound. Browser-session incident history does not persist across page reloads and requires no new database tables or API contracts. Test active failure, repeated failure, recovery, subsequent outage, bounded eviction, and recovery of one transport while another remains unavailable.

### 4. Snapshot reconciliation rather than reliable delivery assumptions

Add GET /api/v1/dashboard/snapshot, GET /api/v1/events, GET /api/v1/counts/timeseries and WebSocket /api/v1/dashboard/live. Keep existing read routes unchanged. Default event page size 6, maximum 100; default graph last 30 minutes with one-minute buckets and maximum requested span 24 hours. Filter by car ID, zero-fill empty buckets, and validate bounds.

The API subscribes to Redis before taking the initial snapshot, buffers/coalesces invalidations while reading, then sends the snapshot followed by a refreshed snapshot if anything changed. Each WebSocket connection sends monotonically numbered envelopes; run UUID changes force runtime-state reset. Notifications are invalidations or authoritative replacements, never instructions to blindly increment totals. Saved rows are keyed by BagEvent.id. Reconnect always fetches a new snapshot; reconcile database facts every 5 seconds even without notifications. Thus a lost post-commit publication eventually repairs itself without pretending Redis Pub/Sub is durable.

Each browser connection has a bounded send queue and send timeout; slow clients cannot hold a global lock around network writes. Lifespan ownership belongs to FastAPI for subscriptions and tasks. Fall back to snapshot polling when WebSocket is unavailable; stop polling when the page closes. Celery is not in the immediate refresh path.

### 5. Last detection and preview

Publish a run-scoped track reference, observation time, known classification and processing state; expose an expiring, size-limited latest thumbnail when feasible. Last detection does not mean saved count. No history of every raw detector frame is stored. Default selection for multiple new detections is most recently observed confirmed track, tie-broken by track ID; before confirmation show the highest-confidence candidate as unconfirmed.

Every processed frame may update the latest observation independently of the 0.5-second publication cadence. Preserve the selected metadata and a bounded thumbnail candidate immediately; perform JPEG encoding/network delivery in the worker. A newer observation may replace an older one, but a subsequent empty frame must not clear it. Thumbnail expiry remains independent of retained metadata, and an image must correspond to the selected observation or be explicitly unavailable. Render the existing null track reference as an explicit Unconfirmed state, separately from Unknown classification, without renaming payload fields or changing saved-count semantics. Regress an empty frame at t=0, one candidate at t=100 ms, and an empty frame at t=600 ms: the next publication/render still shows the candidate and its observation time, while saved totals remain unchanged.

Retain MJPEG initially through the existing API endpoint and same-origin URL. Its independent preview connection must not drive counting-camera health; label absence explicitly. Sharing capture and annotated preview is a later optimization, not a prerequisite to honest status. Clip paths and FFmpeg extraction are unchanged; available preview is not proof that an event clip exists.

### 6. Manual number correction without ownership changes

PATCH /api/v1/wagons/{id} accepts number and expected revision. Add Wagon.revision with an additive migration and default 0. In one short write transaction verify there is exactly one active car and that it matches the ID, then conditionally update its number and revision. Return 409 for stale revision or ambiguous context, validation errors for blank/overlong numbers, and current car state. Preserve leading zeros. A lost response is reconciled by GET; a repeated request with an old revision cannot apply a second mutation.

The browser edits the currently active row, including replacing startup W001 with the real number. It does not create, close or transfer cars. Keeping the same ID avoids the pipeline's cached wagon-identity problem for this operation. No changes are made to existing BagEvent references, shift IDs or count totals. Two screens receive the corrected number after invalidation/reconciliation. If no unique active car exists, show an actionable context error and disable correction.

### 7. Minimal usable operator authentication

Implement the already advertised POST /api/v1/auth/login using configured operator credentials and HS256 expiring bearer tokens compatible with existing protected tasks. Validate login input, rate-limit failures, and avoid logging credentials. Browser holds the token in memory, requests login for edits and prompts again after expiry; do not put tokens in URLs or persistent browser storage. Read visibility follows the existing local API policy. Login is same-origin; document HTTPS for deployments beyond a trusted kiosk network. No user directory, external identity provider or role hierarchy is introduced.

Use API_ADMIN_USER and API_ADMIN_PASS as the canonical application environment names. The main, 2CPU and 4CPU Compose variants must map existing ADMIN_USERNAME/ADMIN_PASSWORD inputs into those names, with explicitly configured canonical values taking precedence. Preserve the existing Compose fallback policy when neither form is supplied; do not change real secrets. Limit the correction to operator credential wiring rather than refactoring unrelated Settings aliases. Authentication tests must initialize Settings from deployment environment variables and call the actual login/protected routes; monkeypatching Settings fields alone does not establish this integration. Cover legacy names, canonical names and both forms with the documented precedence, plus invalid credentials and existing protected-task compatibility.

### 8. Deployment and migration boundaries

Route / to static UI and /api/ including live WebSocket/MJPEG to FastAPI. Preserve existing /ws consumers by explicitly routing /ws/ to FastAPI where supported. Retain Redis, SQLite mounts, NVR and monitoring. Ensure worker/beat execute their supplied command rather than the CV entrypoint; audit main, 2CPU and 4CPU variants consistently. This does not add a distributed counting lease.

Use an explicit, rerunnable additive migration for Wagon.revision and (wagon_id,counted_at,id) event-query index. Schema creation alone does not upgrade existing SQLite tables. Database sessions belong to individual API requests; the replacement UI has no direct database connection.

## Risks / Trade-offs

- Existing exactly-once/counting defects remain -> distinguish detected from saved events and test instrumentation against unchanged deterministic trajectories; do not imply a correctness repair.
- Camera or inference latency causes false Offline -> configurable deadlines, separate stage status, target-hardware verification.
- Redis loss -> retained database history, visibly unavailable telemetry and bounded producer work; periodic reconciliation after recovery.
- Browser-local clock can be wrong -> follow requested computer time while retaining canonical UTC event timestamps.
- Legacy maintenance UI can still switch cars unsafely -> disable it by default during normal operation and document the existing cached-context limitation; do not expose those actions in the new screen.
- Additive scope includes authentication and telemetry -> these are required for accurate status and API-backed edits; keep notification/report and model defects out of this change.

## Migration Plan

1. Back up SQLite and record baseline event/car IDs and totals; stop services for migration.
2. Apply and verify additive migration; never delete or reassign events.
3. Deploy corrected service roles, API and nonblocking telemetry; verify one CV producer and bounded runtime overhead on the target CPU.
4. Deploy static UI and switch nginx root; smoke-test login, edit, video, graph and reconnect on the kiosk.
5. Keep legacy UI as opt-in maintenance fallback. Roll back the UI route and compatible API image if necessary; retain additive columns/indexes and preserve corrected car numbers. Do not restore an old database backup over newly counted events.

## Verification acceptance gate

Before archive, close all five confirmed gaps with regressions: brief-detection retention; deployment-environment authentication; timestamped communication failure/recovery history; desktop fit at and around the 950-pixel breakpoint; and exact UTC time-series boundaries. Reconcile the 0.5-second heartbeat and explicit Unconfirmed presentation as part of that work. Rerun the affected backend/browser and compatibility checks and refresh the verification record; prior passing tests do not establish the newly specified cases.

Tasks 8.2, 9.3 and 9.5 remain pending until actual service-role, physical kiosk/camera, and copied-storage/target-CPU acceptance is performed. Local tests and planning updates cannot substitute for that evidence.

## Open Questions

- Final color palette and operator-language wording can be refined during visual review without changing the contracts.
- Confirm physical kiosk dimensions during acceptance; 1366x768, 1500x950, 1920x950 and 1920x1080, plus breakpoint-adjacent sizes, remain required automated desktop checks.
