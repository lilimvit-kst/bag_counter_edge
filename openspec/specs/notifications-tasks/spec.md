# Notifications and Background Tasks Specification

## Purpose

Define asynchronous operational work and outbound wagon/report notifications without blocking critical API or counting paths.

## Requirements

### Requirement: Wagon report construction
The system SHALL be able to build a wagon report from persisted wagon and bag-event data.

#### Scenario: Wagon exists
- **WHEN** a report is requested for an existing wagon
- **THEN** the report includes wagon number, operator, start/end times, total bags, counts by operational class, estimated total weight, average estimated volume, and up to a small set of clip paths

#### Scenario: Wagon does not exist
- **WHEN** report construction is requested for an unknown wagon ID
- **THEN** no wagon report is produced

### Requirement: Optional email and Telegram delivery
The system SHALL send wagon reports only through notification channels that have sufficient configuration to operate.

#### Scenario: Email channel is not configured
- **WHEN** required SMTP/email settings are absent
- **THEN** email delivery is skipped and reported as not sent

#### Scenario: Telegram channel is configured
- **WHEN** bot token and chat ID are configured and Telegram accepts the request
- **THEN** the system reports successful Telegram delivery

### Requirement: Notification failures are contained
Notification delivery failure SHALL be logged and SHALL NOT crash the primary bag-counting pipeline.

#### Scenario: External notification provider fails
- **WHEN** email or Telegram delivery raises an exception
- **THEN** the failure is logged
- **AND** the notification call reports failure to its caller

### Requirement: Queue-backed background work
The deployment SHALL support queueing I/O-bound report, notification, dashboard, cleanup, and media-processing work to Celery workers when those task paths are used.

#### Scenario: Task is submitted through the API
- **WHEN** an authenticated API task trigger accepts a request
- **THEN** Celery receives asynchronous work through the configured broker
