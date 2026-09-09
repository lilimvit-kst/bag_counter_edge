# Implementation verification — 2026-09-09

30 of 33 tasks are complete. The remaining software work, including all five
confirmed verification gaps, is implemented and covered by regressions. The three
remaining tasks require deployment or target hardware acceptance. This change
has not been deployed or archived, and production storage has not been migrated.

## Verification dimensions

| Dimension | Finding |
|---|---|
| Completeness | 30/33 tasks complete; implementations located for all 15 delta requirements. Three target acceptance tasks remain open. |
| Correctness | Five confirmed gaps closed; 65 dashboard tests pass. Built-container, physical-camera and copied-storage/target-CPU acceptance remain unverified. |
| Coherence | Existing backend/API contracts, counting rules and persistence semantics preserved; implementation and guide agree on 0.5-second publication, immediate observation retention and page-session incident history. |

## Follow-up fixes and regression evidence

| Confirmed gap | Implementation | Passing evidence |
|---|---|---|
| Detection retention | `src/dashboard/telemetry.py:85` removes observation-time throttling; retains one bounded copied crop and metadata, with JPEG/network work in the worker. `frontend/app.js:361` labels a null track reference Unconfirmed independently of Unknown class. | `test_brief_detection_is_retained_between_publications` exercises empty/detection/empty at 0/100/600 ms, exact observation time, crop identity and expiry. Real Redis/API/browser acceptance retains the brief candidate without increasing saved totals. |
| Deployment credentials | All three Compose variants map legacy inputs to canonical settings, with nonempty canonical precedence and existing fallbacks. | Nine environment-initialized authentication cases cover legacy-only, canonical-only and conflicting inputs through actual login/protected routes. Fallback tests use the actual Compose expressions; integrated browser login uses the expanded legacy deployment inputs. |
| Communication history | `frontend/app.js:79` retains at most 20 timestamped incident episodes, groups repeated reports, records recovery and evicts recovered episodes first. HTTP, WebSocket and Redis recover independently; fresh HTTP facts preserve model status during WebSocket loss. Runtime/derived warnings merge by code. | Browser tests cover repeat reports, subsequent outages, independent transport recovery, CV run changes, bounded retention, safe persistence messages and recovery details. Missing runtime data cannot falsely recover camera faults. Real process restart acceptance preserves incident details and reconciles counts in the same document. |
| Viewport overflow | `frontend/styles.css:629` enlarges the desktop layout only from 1000 pixels in height, leaving enough room for its header, cards, alerts and footer. | Browser tests in two timezones cover 1366×768, 1500×950, 1920×950, 1920×1080, widths 1499/1500/1920 and heights 949/950/951/999/1000/1001. Required elements and six rows remain visible; 1080p retains the 86-pixel count. |
| Time-series precision | `src/dashboard/queries.py:59` streams car-scoped timestamps and uses exact UTC datetime comparisons and minute flooring, preserving stored timestamps and response shapes. | Eighteen boundary cases cover one microsecond before/at/after start and end with naive UTC, UTC offsets and +05:00. Another test covers fractional offset bounds and bucket assignment across the final microsecond of a minute. |

The runtime publisher, specifications and guide consistently use the existing
0.5-second heartbeat/publication default and 5-second expiry. This cadence does
not throttle observation retention. Incident history is browser-page memory, not
a new durable alert API or database log.

## Requirement coverage

| Delta requirement | Implementation and automated coverage |
|---|---|
| Existing API compatibility | `src/api/app.py`, `test_compatibility.py`: established reads, protected tasks, WebSocket envelopes and MJPEG. |
| Dashboard snapshot and historical queries | `src/dashboard/queries.py`, `test_queries.py`, `test_api.py`: consistent transaction, scoping, limits, pagination and exact UTC bounds. |
| Reconciled live dashboard delivery | `src/dashboard/api.py`, `telemetry.py`, `test_realtime.py`, `test_api.py`: reconnect, missed/duplicate notifications, snapshot races, slow-client cleanup and brief observations. |
| Operator login for car edits | `src/dashboard/api.py`, `test_api.py`, `test_compatibility.py`: configured environment, invalid credentials, expiry, rate limits and compatible protected endpoints. |
| Compact operator overview | `frontend/index.html`, `styles.css`, `test_browser.py`: desktop breakpoints, six rows, large count, history/video expansion and mobile access. |
| Truthful counting status | `derive_status`, `connectionStatus`, telemetry/browser/process tests: startup, empty conveyor, stalled/stopped model, camera loss and unavailable transport. Physical checks remain task 9.3. |
| Local time and stable rendering | `frontend/app.js`, browser tests: Almaty/New York timestamps, fixed title/document, preserved typing/focus and server-clock correction. |
| Separate detection from saved counts | `RuntimePublisher.observe`, `render`, telemetry/pipeline/process tests: confirmed/unconfirmed states, unknown class, retained brief detection, image identity/expiry and committed totals. |
| Scoped count history | `queries.series`, `history`, query/browser/pipeline tests: current-car scope, zero filling, empty context and unchanged associations. |
| Operator-facing alerts | `recordIncident`, `runtimeIncidents`, `alerts`, telemetry/browser/process tests: grouped faults, timestamped recovery, dependency-specific incidents, bound and safe messages. |
| Local operator dashboard delivery | Static image and nginx/Compose routes, deployment/browser/process tests: local assets and same-origin API, WebSocket and video. Built-stack checks remain task 8.2. |
| Correct service roles | Entrypoint and Compose configuration, shell/static deployment tests. Actual built worker/beat roles and one producer remain task 8.2. |
| Operator credential environment mapping | Three Compose mappings, fallback tests, nine environment-initialized auth cases and integrated browser login. |
| Manual active-car number entry | `correct_car`, API/browser/process tests: string validation, leading zeros, same ID/count/ownership and conflict retry. |
| Safe concurrent car correction | SQLite write transaction and revision check, query/API/browser/process tests: simultaneous edits, stale revisions, absent/ambiguous context and preserved input. |

## Automated evidence

- The final complete dashboard suite passed **65 tests**, with no failures or
  skips, in 53.33 seconds (42 dependency warnings), including a real isolated
  Redis server, a separate Uvicorn API process and Chromium WebSocket delivery.
  It includes all 11 pipeline/telemetry tests and 9 browser cases.
- Browser checks cover all required desktop sizes and adjacent breakpoints without page scrolling, six visible
  recent events, mobile access, Almaty/New York local timestamps, a stable title
  and document, preserved form focus, conflicts, history drawer, fullscreen
  preview, missing images, empty data, warning recovery and server-clock rollback.
- Real process tests stop/restart Redis and the API, replace the CV run identity,
  commit rows without notifications, publish duplicate notifications and verify
  authoritative totals recover in the same browser document. An injected commit
  failure passes through the actual counting method, Redis, API and browser;
  the warning appears without adding a saved count. Operator login and revision
  conflict/retry use the actual HTTP routes.
- Focused WebSocket tests exercise a commit during initial snapshot delivery and
  bounded cleanup of a client that cannot receive a snapshot. Invalidations are
  coalesced independently of client send speed.
- Synthetic replay runs real tracking, tripwire, handover and count persistence
  with fixed inference outputs. Telemetry enabled/disabled both save one bag;
  committed rows, current-car total, graph and recent events agree. Model accuracy
  and physical-bag exactly-once behavior are not established by this replay.
- SQLite migration tests preserve populated event IDs, ownership, totals and clip
  paths, and verify reruns. Query/authentication tests cover pagination, intervals,
  class totals, absent/ambiguous car context, leading zeros and concurrent edits.
- Existing read/task response contracts, operator-token compatibility, legacy
  WebSocket message envelopes and MJPEG headers/JPEG placeholder were checked.
- JavaScript syntax, shell syntax, `git diff --check`, Compose YAML/route checks
  and `openspec validate redesign-operator-dashboard --strict` pass.
- `openspec validate --all --strict`: **13 passed, 0 failed**.

Tests used an isolated Python 3.11 environment with deployment versions FastAPI
0.111.0 and Uvicorn 0.30.0. Chromium, fonts, libraries and Redis binaries were
installed under `/tmp`. No camera connection or external notification was made.
See [the operator guide](../../../docs/operator-dashboard.md) for reproducible
test commands and the optional Redis executable setting.

## Existing regression failures

The existing API/notification suite was rerun and reports **11 passed, 3 failed**
in 1.30 seconds. These are the same three failures previously reproduced during
baseline verification on an isolated copy of unchanged Git HEAD with the same
workspace configuration:

1. `test_health_check`: the earlier metrics router returns `healthy` and metrics
   fields; the test expects only `status: ok`.
2. `test_active_wagon_no_auth`: the in-memory SQLite test fixture uses different
   connections across threads and reaches a connection without the tables.
3. `test_telegram_disabled_when_not_configured`: the test assumes Telegram is
   unconfigured, while this workspace has configuration. It passes when running
   the baseline without the workspace configuration.

These existing behaviors and tests were preserved. No secrets were copied into
the baseline fixture or changed.

## Outstanding acceptance — three critical archive gates

- **8.2:** entrypoint command dispatch and all Compose variants are corrected;
  shell dispatch and configuration tests pass. Worker health uses Celery ping,
  and beat no longer inherits the API HTTP check. Docker is unavailable in this
  environment, so actual built-container worker/beat execution and exactly one
  intended CV process still need verification on the deployment host.
- **9.3:** physical kiosk/camera verification remains required for real frame
  freshness/reconnect, model lifecycle, loading, count visibility, number
  correction, warnings and readability on the operator's display.
- **9.5:** migration on synthetic populated SQLite is verified. Rehearsal on a
  copy of deployment storage, actual UI rollback and telemetry/inference timing
  on target CPU hardware remain required. Confirm the 15-second processing and
  5-second capture deadlines against the real model and camera.

Before rollout, run the explicit additive migration described in the operator
guide with writers stopped and a verified backup. Retain the added revision
column/index during UI rollback; do not restore a stale database over new counts.

No additional confirmed software gap remains from this review. Complete the
specific target checks in 8.2, 9.3 and 9.5 before archive; automated tests and
artifact validation do not establish that acceptance. Exact time-series reads
are bounded in memory and use the car index but scan that car's timestamp history;
include representative history size in the outstanding target performance checks.
