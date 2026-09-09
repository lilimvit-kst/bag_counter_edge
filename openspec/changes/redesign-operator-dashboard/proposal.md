## Why

Operators need a stable, readable loading screen with a prominent bag count and trustworthy equipment status. The current Streamlit dashboard continuously reruns, permanently displays Offline, and lacks pipeline health, time-series history, and reliable car-number entry.

## What Changes

- Keep the existing FastAPI backend, SQLite persistence, background services and established HTTP/WebSocket contracts. Add only the data, status, delivery and car-entry capabilities required by the operator dashboard; unrelated backend refactors and existing endpoint behavior changes are excluded.
- Replace the primary Streamlit screen with a compact browser dashboard: large current-car count, class totals, camera/detector/tracker status, last detection, recent saved counts, counts-over-time graph, and actionable alerts.
- Use the viewing computer's local time and a stable Bag Counter browser title; update components without full-page refresh and keep primary information visible at 1366x768 and larger.
- Add FastAPI dashboard snapshots, scoped history and time-series queries, and cross-process runtime telemetry with reconnect reconciliation.
- Retain the latest detection immediately, including observations visible for less than 500 ms; coalesce publication/render work rather than observation capture. Use the implemented 0.5-second heartbeat as the documented default and clearly label unconfirmed detections.
- Preserve bounded, timestamped communication incident history with active and recovered details in the browser session. Recovery may clear the active-warning summary but must not erase incident context.
- Align operator credentials across the main, 2CPU and 4CPU Compose configurations and application settings; cover login using deployment environment variables.
- Close verified presentation/query gaps: fit 1500x950 and 1920x950 as well as the existing desktop targets, and preserve UTC microsecond precision for half-open time-series intervals.
- Add manual correction of the active car number through an authenticated API. One car is filled at a time; corrections retain its identity and event associations. Bag transfers and overlapping loading sessions are excluded.
- Retain existing count decisions, YOLO model/class filtering, tracker, volume thresholds, tripwire/handover rules, SQLite events, and clip allocation behavior. Telemetry reports successful persistence separately from detection.
- **BREAKING**: The primary operator route becomes the new dashboard rather than the Streamlit application. Existing read APIs remain available; legacy maintenance access is explicitly separated.

## Capabilities

### New Capabilities
- `operator-car-entry`: Authorized manual entry/correction of the current car number without changing bag ownership.

### Modified Capabilities
- `dashboard-monitoring`: Compact operator presentation, local time, stable updates, truthful runtime status, recent activity and alerts.
- `api-realtime`: Dashboard snapshot/history/time-series endpoints, runtime telemetry delivery, resynchronization, and usable operator authentication.
- `deployment`: Serve the new UI locally and route its API/realtime traffic with correct service roles.

## Impact

- UI: replace primary usage of src/kiosk/dashboard.py with local browser assets; retain Streamlit only as a temporary maintenance fallback.
- Backend: src/api/app.py, src/websocket/manager.py, src/main.py and src/capture/camera_stream.py gain dashboard contracts and nonblocking instrumentation. Detector/tracker processing algorithms remain unchanged.
- Storage: retain Shift, Wagon and BagEvent; add optimistic car revision and query indexes through an explicit SQLite migration. Never rewrite historical event ownership or evidence paths.
- Deployment: nginx, dashboard image, Compose variants and entrypoints; use existing Redis for transient telemetry. No cloud services or model migration. Browser assets require no ML runtime.
- Authentication: complete a minimal configured-operator login contract for car edits; preserve existing JWT-protected task interfaces.
- Rollout: back up SQLite, apply additive migration, deploy API/telemetry before switching the UI route. Roll back UI routing first; additive database changes remain compatible.
- Known counting/persistence defects in BASELINE_AUDIT.md and the review remain separate work. Fix service command dispatch to avoid unintentionally launching CV in worker/beat roles; this is a deployment prerequisite, not a tracker redesign.

## Verification follow-up and archive gate

Verification confirmed five gaps in this dashboard change: observation throttling can discard a brief detection; advertised Compose credential aliases do not reach login settings; communication recovery erases incident context; the enlarged layout scrolls at 950-pixel desktop height; and rounded time comparisons exclude a valid event just before an interval end. All five require fixes and regression coverage before archive. These corrections preserve existing backend/API contracts and do not expand into counting-rule or persistence-retry repairs.

Tasks 8.2, 9.3 and 9.5 remain open until their actual deployment/runtime, physical kiosk/camera, and target storage/CPU checks are performed. Updating planning artifacts or passing local automated tests does not complete those tasks.
