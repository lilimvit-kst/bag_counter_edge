## 1. Proposal preparation

- [x] 1.1 Review the current dashboard, API, realtime mechanism and baseline audit; verified findings are recorded in design.md Context.
- [x] 1.2 Prepare the operator-focused proposal and define required backend additions, compatibility boundaries and exclusions; verified in proposal.md What Changes and Impact.

## 2. Requirements

- [x] 2.1 Specify one-screen monitoring, large counts, component status, last detection, recent events, graph, alerts, local time and stable title; verified in specs/dashboard-monitoring/spec.md scenarios.
- [x] 2.2 Specify single-active-car manual entry without transfers and preserve existing API contracts; verified in specs/operator-car-entry/spec.md and specs/api-realtime/spec.md.
- [x] 2.3 Define local deployment and correct service roles; verified in specs/deployment/spec.md.

## 3. Design preparation

- [x] 3.1 Document browser layout, retained services, necessary API additions, telemetry ownership and reconnect behavior; verified in design.md Decisions.
- [x] 3.2 Document additive migration, rollback, operational risks and acceptance approach; verified in design.md and implementation tasks below.

Planning milestones above are complete. Verification follow-up reopens affected implementation tasks below; their earlier passing checks did not cover the confirmed gaps. Check a task only after its revised behavior and regression coverage pass. Planning edits do not implement fixes or complete target/runtime acceptance.

## 4. Database and dashboard queries

- [x] 4.1 Add explicit rerunnable migration for Wagon.revision and car/time event index; verify migration on a populated temporary SQLite fixture preserves event IDs, totals, associations and clip paths.
- [x] 4.2 Implement request-scoped dashboard snapshot queries with consistent durable totals, unique active-car handling and UTC timestamp serialization; verify empty, populated and ambiguous-context fixtures.
- [x] 4.3 Complete bounded paginated event and zero-filled time-series queries by replacing rounded julianday boundary comparisons with precision-preserving UTC filtering and bucket assignment. Preserve stored timestamps and API shapes; verify car isolation, empty buckets, pagination, invalid input, and one microsecond before/exactly at/one microsecond after both [start,end) boundaries using naive UTC and offset-qualified values. Include 10:00:59.999999 in [10:00,10:01).

## 5. Runtime telemetry

- [x] 5.1 Add bounded asynchronous runtime publisher with source/run identity, expiry and shutdown ownership; verify Redis failure, timeout and queue saturation cannot block frame processing.
- [x] 5.2 Instrument actual capture success, model initialization, detector/tracker progress and last detection without changing tracking/crossing rules; verify fake-camera trajectories produce identical count decisions with telemetry enabled and disabled.
- [x] 5.3 Publish saved-count notifications only after commit and grouped operational error/recovery state; verify commit failure never emits a saved count and repeated warnings stay bounded.
- [x] 5.4 Retain the latest selected detection observation immediately and keep only publication/render work throttled at the 0.5-second cadence. Empty frames must not erase it; keep thumbnail candidates bounded and encoding/network work off the CV loop. Add the empty-at-0/detected-at-100-ms/empty-at-600-ms regression and verify retained observation time, unchanged saved totals, null track reference for unconfirmed candidates, unknown class, multiple candidates, thumbnail identity/expiry and missing-image states without leaking camera URLs.
- [x] 5.5 Derive service/component statuses using heartbeat and stage freshness; verify startup, empty conveyor, camera outage, stopped model, stuck inference and unavailable transport using a controlled clock.

## 6. API realtime and operator access

- [x] 6.1 Implement dashboard WebSocket subscription, initial snapshot reconciliation, bounded client queues and periodic durable refresh; verify duplicate/missed notifications, snapshot races, process restart and slow clients.
- [x] 6.2 Complete configured-operator login coverage with expiring compatible JWTs and rate-limited failures. Using the deployment mapping in task 8.4, initialize Settings from environment variables and test actual login for legacy-only, canonical-only and conflicting inputs with canonical precedence; verify invalid credentials, expired tokens and existing protected task endpoints without relying solely on monkeypatched Settings fields.
- [x] 6.3 Add authenticated active-car number correction with revision conflict detection; verify leading zeros, whitespace, length, simultaneous edits, response retry and unchanged event ownership/counts.

## 7. Operator interface

- [x] 7.1 Correct the responsive overview sizing so required content fits 1366x768, 1500x950, 1920x950 and 1920x1080 without document scrolling or hidden required content. Add breakpoint regressions at 1499/1500-pixel widths and 949/950/951-pixel heights; preserve the readable large count, preview, graph, component states, car number and six visible recent events at 1920x1080, plus smaller-screen access.
- [x] 7.2 Add local-time clock, event/chart formatting and fixed Bag Counter title; verify two browser timezones and stable title/document during continuous live updates.
- [x] 7.3 Connect snapshot, live updates, fallback polling and stale-state indicators; verify disconnect/reconnect repairs data without inflating totals or presenting stale status as current.
- [x] 7.4 Complete the last-detection card with an explicit Unconfirmed label for candidates without a confirmed track reference, distinct from Unknown classification. Verify a sub-500-ms observation survives the next publication/render without changing saved totals; retain graph/history/fullscreen-preview behavior and verify empty data, precise/sparse buckets, missing images and camera failure states.
- [x] 7.5 Add login and persistent car-number form with keyboard access and conflict/error feedback; verify live updates preserve typed text and focus, and successful save keeps the same car/event IDs.
- [x] 7.6 Maintain a bounded browser-session history of at most 20 timestamped communication/derived-status incident episodes alongside grouped runtime warnings. Preserve active/recovered details across snapshot replacement, coalesce repeated active reports, record recovery time, start a new episode for a subsequent outage and evict oldest recovered episodes first. Test disconnect/reconnect details, independent HTTP/WebSocket/Redis recovery, repeated outages, bounded retention, persistence warnings and no credential/path/stack-trace exposure; No active warnings must not erase recovered context from the details drawer.

## 8. Deployment and documentation

- [x] 8.1 Replace primary dashboard delivery with a lightweight static asset service and same-origin API/live/video routing; verify nginx paths and offline asset loading, keeping legacy read routes accessible.
- [ ] 8.2 Correct worker/beat command dispatch and align Compose variants; verify actual service process roles contain one intended CV producer and working Celery worker/beat commands.
- [x] 8.3 Reconcile the operator guide with the 0.5-second heartbeat/publication default, immediate observation retention, Unconfirmed presentation, bounded browser-session incident history and canonical/legacy credential precedence. Retain single-car correction, migration, rollout/rollback and opt-in legacy maintenance limitations; verify documented commands/defaults against configuration without editing secrets.
- [x] 8.4 Map ADMIN_USERNAME/ADMIN_PASSWORD to API_ADMIN_USER/API_ADMIN_PASS consistently in docker-compose.yml, docker-compose-2CPU.yml and docker-compose-4CPU.yml, giving explicit canonical settings precedence and preserving existing Compose fallbacks. Add deployment environment/configuration coverage and use the resulting environment for task 6.2 authentication tests; preserve backend/API contracts and unrelated Settings aliases.

## 9. Integrated acceptance

- [x] 9.1 After all five gap fixes, run their focused backend/browser regressions and existing relevant API/notification compatibility checks, then repeat strict OpenSpec validation and verification. Refresh the verification record with current task/test results and evidence for short-lived observations, environment-configured authentication, incident recovery history, intermediate desktop sizes and exact UTC boundaries; distinguish pre-existing unrelated failures and unresolved target/runtime acceptance.
- [x] 9.2 Replay deterministic prerecorded or synthetic video through the instrumented counting path with temporary storage; verify unchanged count decisions and agreement between committed rows, dashboard totals, graph and recent events.
- [ ] 9.3 Perform manual kiosk/camera verification for fresh/stale frames, camera reconnect, model stop/start, no bags, last detection, saved count, car correction and warnings; verify no tab blinking, minimal scrolling and readable large count on the target display.
- [x] 9.4 Re-exercise Redis/API restart, browser disconnect, duplicate notification, database write failure and car-edit conflict end to end after the follow-up fixes. Verify truthful status, retained timestamped active/recovered communication incidents through reconnect, dependency-specific recovery and eventual database reconciliation without count inflation; include deployment-configured login and retained brief-detection presentation in integrated acceptance.
- [ ] 9.5 Rehearse migration and UI rollback on copied storage and measure telemetry overhead on target CPU hardware; verify no event loss/reassignment, bounded queues and suitable processing deadlines before rollout.

[verification.md](verification.md) records the completed follow-up fixes, 65 passing
dashboard tests, relevant regression results and the remaining acceptance gates.
This task list and design.md's verification gate define current acceptance.

Tasks 8.2, 9.3 and 9.5 remain unchecked until their actual target/runtime checks
are performed. Automated regressions and artifact validation do not complete them.
