# Bag Tracking Specification

## Purpose

Define persistent bag identity behavior across adjacent frames so that the same physical bag can be reasoned about over time and counted at most once per track lifecycle.

## Requirements

### Requirement: Persistent track identity
The system SHALL associate qualifying detections across frames with persistent track identifiers when their observed motion and overlap are compatible with the active tracking rules.

#### Scenario: Existing bag is matched
- **GIVEN** an active track and a new detection that satisfies the association threshold
- **WHEN** a tracking update is performed
- **THEN** the existing track identifier is retained for that detection
- **AND** the track state and confidence are updated

#### Scenario: New unmatched bag appears
- **WHEN** a qualifying detection cannot be associated with an existing track
- **THEN** the system creates a new track with a new identifier

### Requirement: Track confirmation
The system SHALL expose a track to downstream counting only after it has accumulated the configured minimum number of observations.

#### Scenario: Track is not yet confirmed
- **WHEN** a track has fewer observations than the configured minimum hits
- **THEN** it is not returned as an active confirmed track

### Requirement: Temporary disappearance tolerance
The system SHALL retain a track for a configured age while detections are temporarily absent so handover/occlusion logic can reason about disappearance.

#### Scenario: Bag is briefly occluded
- **WHEN** an existing track is unmatched for fewer than or equal to the configured maximum disappearance age
- **THEN** the track remains available with an incremented disappearance count

#### Scenario: Track becomes stale
- **WHEN** a track remains unmatched beyond the configured maximum age
- **THEN** the tracker removes that track from active state

### Requirement: Counting state is track-scoped
The system SHALL preserve whether an active track has already been counted for the lifetime of that track.

#### Scenario: Counted track remains active
- **GIVEN** a track has been marked counted
- **WHEN** it continues to be observed in later frames
- **THEN** its counted state remains true
