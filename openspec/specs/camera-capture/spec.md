# Camera Capture Specification

## Purpose

Define the observable video-input behavior required by the edge counting pipeline, including continuous frame availability, timestamps, reconnect handling, and optional synchronized secondary capture.

## Requirements

### Requirement: Primary camera frame delivery
The system SHALL provide the counting pipeline with frames from the configured primary camera source together with a capture timestamp and a success indicator.

#### Scenario: Frame is available
- **GIVEN** the primary camera source is reachable
- **WHEN** the pipeline requests the latest frame
- **THEN** the system returns a successful result with a non-empty frame
- **AND** returns a timestamp associated with that captured frame

#### Scenario: Frame is temporarily unavailable
- **WHEN** no valid frame is currently available
- **THEN** the capture interface returns an unsuccessful result without terminating the counting process

### Requirement: Camera reconnect behavior
The system SHALL attempt to recover from an interrupted primary camera stream instead of requiring an application restart for a transient disconnect.

#### Scenario: Stream read fails
- **GIVEN** the camera was previously running
- **WHEN** frame acquisition fails repeatedly
- **THEN** the camera subsystem attempts reconnection according to configured retry and delay limits

### Requirement: Controlled camera lifecycle
The system SHALL support explicit start and stop lifecycle operations for camera resources.

#### Scenario: Pipeline shuts down
- **WHEN** the counting pipeline is stopped
- **THEN** camera acquisition is stopped and the underlying capture resource is released

### Requirement: Optional paired capture
The system SHALL support optional paired-frame capture when a secondary camera is configured.

#### Scenario: Paired streams are configured
- **WHEN** synchronized capture is requested from two active sources
- **THEN** the system returns a frame from each source as one logical capture result
