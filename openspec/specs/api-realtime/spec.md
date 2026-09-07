# API and Realtime Specification

## Purpose

Define locally exposed service interfaces for health, bag statistics, active wagon state, task submission, WebSocket updates, monitoring, and live video.

## Requirements

### Requirement: Basic health endpoint
The API SHALL expose a health endpoint that can be used by deployment health checks.

#### Scenario: API process is healthy
- **WHEN** a client requests `/health`
- **THEN** the service returns a successful response containing status `ok`

### Requirement: Active wagon query
The API SHALL expose the current active wagon when one exists.

#### Scenario: Active wagon exists
- **WHEN** a client requests `/api/v1/wagons/active`
- **THEN** the response includes the wagon ID, wagon number, and start time

#### Scenario: No active wagon exists
- **WHEN** no wagon is active
- **THEN** the response indicates that there is no active wagon

### Requirement: Aggregate bag statistics
The API SHALL expose total stored bag-event count and counts grouped by the operational bag classes.

#### Scenario: Statistics are requested
- **WHEN** a client requests `/api/v1/stats/today`
- **THEN** the response includes `total_counted`
- **AND** includes counts for `25kg`, `50kg`, and `empty`

### Requirement: Protected asynchronous task submission
Task-trigger endpoints SHALL reject unauthenticated requests and SHALL enqueue accepted work without waiting for task completion.

#### Scenario: Protected task request has no valid JWT
- **WHEN** a client calls a protected task endpoint without a valid bearer token
- **THEN** the API responds with HTTP 401

#### Scenario: Authenticated task request is accepted
- **WHEN** a client with a valid JWT submits valid task input
- **THEN** the API queues the task
- **AND** returns a task identifier and queued status without waiting for the result

### Requirement: WebSocket channel delivery
The API SHALL provide WebSocket channels for general, dashboard, event, and alert messages and SHALL allow connected clients to subscribe or unsubscribe from channels.

#### Scenario: Client subscribes to a channel
- **WHEN** a connected WebSocket client sends a valid subscribe command
- **THEN** subsequent broadcasts for that channel are eligible for delivery to that client

### Requirement: Live MJPEG stream
The API SHALL expose a multipart MJPEG video stream for local dashboard/browser consumption.

#### Scenario: Camera frame is available
- **WHEN** a client consumes `/api/v1/video/stream`
- **THEN** JPEG-encoded frames are emitted as multipart stream frames

#### Scenario: Camera frame is unavailable
- **WHEN** the stream cannot obtain a current camera frame
- **THEN** the endpoint emits a placeholder image rather than terminating immediately
