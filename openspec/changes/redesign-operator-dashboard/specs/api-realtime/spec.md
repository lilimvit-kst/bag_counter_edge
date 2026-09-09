## ADDED Requirements

### Requirement: Existing API compatibility
The system SHALL preserve established HTTP routes, request and response contracts, protected task authentication, MJPEG streaming and legacy WebSocket message contracts while adding dashboard functionality. Dashboard-specific contracts SHALL be additive; unrelated endpoint behavior changes are excluded.

#### Scenario: Existing client after dashboard rollout
- **WHEN** an existing client uses an established read, protected task, video or WebSocket interface
- **THEN** its existing request and response contract remains supported independently of the new dashboard

### Requirement: Dashboard snapshot and historical queries
The API SHALL expose a dashboard snapshot containing current-car identity, committed totals, last detection, component health, active alerts, recent saved events and freshness metadata. It SHALL expose bounded, car-scoped paginated event and time-series queries using offset-qualified timestamps and explicit interval boundaries. Time-series filtering and bucket assignment SHALL preserve stored microsecond precision after UTC normalization and SHALL use [start,end) semantics without rounded boundary comparisons. Existing response shapes and persisted timestamps SHALL remain compatible.

#### Scenario: Consistent snapshot
- **WHEN** a dashboard snapshot is requested
- **THEN** its durable totals and recent events describe the same database snapshot and its telemetry includes separate freshness information

#### Scenario: Invalid or excessive history interval
- **WHEN** a request has invalid bounds or exceeds supported limits
- **THEN** the API rejects it with a validation error rather than performing an unbounded query

#### Scenario: Exact start boundary
- **WHEN** saved events occur one microsecond before, exactly at, and one microsecond after the requested start
- **THEN** the event before the start is excluded and the events at and after the start are included if they precede the end

#### Scenario: Exact end boundary
- **WHEN** saved events occur one microsecond before, exactly at, and one microsecond after the requested end
- **THEN** only the event before the end is included if it is at or after the start
- **AND** an event at 10:00:59.999999 is included in [10:00,10:01)

#### Scenario: Equivalent UTC instants
- **WHEN** legacy naive UTC or offset-qualified stored timestamps and query bounds describe equivalent instants near a boundary
- **THEN** normalization produces identical inclusion decisions and minute-bucket placement without rewriting stored events

### Requirement: Reconciled live dashboard delivery
The API SHALL deliver runtime status, detection, saved-count and alert updates from the counting process to browser clients. Duplicate delivery or reconnect SHALL NOT inflate displayed totals. Lost updates SHALL be repaired by snapshot reconciliation. The default runtime heartbeat/publication interval SHALL be 0.5 seconds, allowing at most two publications per second, with a 5-second runtime expiry. Observation retention SHALL NOT be throttled by this interval.

#### Scenario: Disconnect spans a committed count
- **WHEN** a client reconnects after missing or receiving duplicate count notifications
- **THEN** its restored total equals the authoritative persisted total and saved events are deduplicated by event identity

#### Scenario: Telemetry transport fails
- **WHEN** live telemetry transport is unavailable
- **THEN** database history remains queryable, runtime status becomes unavailable, and telemetry publication does not block the counting loop

#### Scenario: Detection between publications
- **WHEN** a detection is observed and disappears before the next 0.5-second publication, with no newer detection replacing it
- **THEN** the next successful snapshot publication includes that retained observation even if intervening frames contain no detections
- **AND** the observation does not increase committed totals

### Requirement: Operator login for car edits
The API SHALL provide a login flow for the configured operator credentials and require a valid expiring session or token for car mutations. Existing protected task authentication SHALL remain supported.

#### Scenario: Authorized operator
- **WHEN** valid configured credentials are submitted
- **THEN** the operator receives an expiring credential usable for car-number correction

#### Scenario: Credentials supplied through deployment environment
- **WHEN** the application starts with operator credentials supplied through the provided deployment configuration
- **THEN** the effective API_ADMIN_USER/API_ADMIN_PASS account can log in and use existing protected task interfaces
- **AND** invalid credentials are rejected, including superseded legacy values when canonical environment values take precedence

#### Scenario: Invalid credentials or expired token
- **WHEN** invalid login credentials or an expired mutation credential are submitted
- **THEN** access is rejected without exposing secrets or changing a car
