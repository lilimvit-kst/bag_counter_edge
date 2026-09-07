# Event Storage Specification

## Purpose

Define durable storage of shifts, wagons, and individual bag count events used by API, dashboard, reporting, and audit workflows.

## Requirements

### Requirement: Persistent bag event
The system SHALL persist each successfully counted bag as a durable event record.

#### Scenario: Count event commit succeeds
- **WHEN** a bag qualifies for counting and database persistence succeeds
- **THEN** the event remains queryable after the current frame-processing iteration

#### Scenario: Count event commit fails
- **WHEN** database persistence raises an error
- **THEN** the transaction is rolled back
- **AND** the failure is logged

### Requirement: Event-to-shift and event-to-wagon association
The system SHALL associate a bag event with the active shift and wagon when those contexts exist.

#### Scenario: Active shift and wagon are present
- **WHEN** a bag is counted
- **THEN** the event stores references to the active shift and active wagon

### Requirement: Startup context availability
The current standalone counting pipeline SHALL ensure an active shift and wagon exist before processing count events.

#### Scenario: No active context exists at startup
- **WHEN** the pipeline initializes and no active shift exists
- **THEN** it creates an active shift
- **AND** if no active wagon exists, it creates an active wagon associated with that shift

### Requirement: Operational bag classes are durable
The database SHALL store bag class using the operational values `empty`, `25kg`, or `50kg`.

#### Scenario: Classified event is persisted
- **WHEN** a counted track has an operational classification
- **THEN** the stored event preserves that classification for later reporting
