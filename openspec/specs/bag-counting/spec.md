# Bag Counting Specification

## Purpose

Define the exactly-once counting decision for a tracked bag as it moves from the conveyor through the handover area.

## Requirements

### Requirement: Directed tripwire crossing
The system SHALL recognize a qualifying crossing only when a confirmed bag track moves across the configured horizontal tripwire from above the line to below it.

#### Scenario: Bag crosses in conveyor-to-worker direction
- **GIVEN** a track center was at or above the tripwire on the previous tracked position
- **WHEN** its current center is below the tripwire
- **THEN** the track is marked as having crossed the tripwire

#### Scenario: Bag moves in the opposite direction
- **WHEN** a track moves from below the tripwire to above it
- **THEN** that motion does not qualify as the required crossing

### Requirement: Handover confirmation before count
The system SHALL count a bag only after its track has crossed the tripwire and the handover logic confirms removal/disappearance according to the configured ROI and disappearance threshold.

#### Scenario: Crossed bag is still inside the ROI
- **GIVEN** a track has crossed the tripwire
- **WHEN** its center remains inside the configured ROI
- **THEN** the system does not count it
- **AND** its handover disappearance counter is reset by the current implementation

#### Scenario: Crossed bag disappears outside the ROI long enough
- **GIVEN** a track has crossed the tripwire and is not already counted
- **WHEN** it is outside the ROI and its disappearance count reaches the configured handover threshold
- **THEN** the system qualifies that track for counting

### Requirement: Exactly once per track
The system SHALL create no more than one count event for a single track identifier during that track's lifetime.

#### Scenario: Count logic is called twice for the same track
- **GIVEN** the track has already been marked counted
- **WHEN** the counting function is evaluated again
- **THEN** no additional bag event is created for that track

### Requirement: Count event captures evidence
The system SHALL associate each successful count with the track's classification, estimated volume, detector confidence, final bounding box, timestamp, and available shift/wagon context.

#### Scenario: Bag is counted
- **WHEN** a track qualifies for counting
- **THEN** a persistent event is prepared with its track ID, count timestamp, class, estimated volume, confidence, bounding-box coordinates, shift/wagon identifiers when available, and an event clip path when one is allocated
