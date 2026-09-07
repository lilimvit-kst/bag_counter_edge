# Event Video Specification

## Purpose

Define continuous/event video behavior used as visual evidence around counted bag events and retention of recorded media.

## Requirements

### Requirement: Count-event clip allocation
The system SHALL allocate an event clip path when a bag count is recorded, without blocking the primary frame-processing loop on clip extraction completion.

#### Scenario: Bag is counted
- **WHEN** a count event is created
- **THEN** clip extraction is submitted asynchronously
- **AND** an expected clip path is returned immediately for association with the event

### Requirement: Event clip time window
The system SHALL build an event clip using the configured pre-event and post-event durations when the selected extraction source supports that time window.

#### Scenario: Clip extraction runs
- **WHEN** an event timestamp is submitted for clip extraction
- **THEN** the requested duration reflects the configured pre-roll plus post-roll interval

### Requirement: Continuous NVR segmentation
The system SHALL support continuous NVR video segmentation when NVR recording is enabled.

#### Scenario: NVR starts
- **WHEN** NVR recording is enabled and the camera source is reachable
- **THEN** the recorder writes timestamped video segments using the configured segment duration

### Requirement: Video retention
The system SHALL support removal of video files older than the configured retention period.

#### Scenario: Recorded media exceeds retention age
- **WHEN** cleanup evaluates a media file older than the retention threshold
- **THEN** that file is eligible for deletion
