## Purpose

Allow an operator to enter or correct the number of the single car currently being filled while preserving all existing bag associations.

## ADDED Requirements

### Requirement: Manual active-car number entry
An authorized operator SHALL be able to edit the number of the active car as a string of 1 to 32 characters after trimming outer whitespace. Leading zeros SHALL be preserved. Saving SHALL retain the car identity, totals, shift and bag-event associations, and SHALL NOT transfer bags or start another loading session.

#### Scenario: Correct the current number
- **WHEN** the operator saves 00123456 for the current car
- **THEN** all connected dashboards eventually show 00123456 and all existing events remain attached to the same car ID

#### Scenario: Invalid number
- **WHEN** the operator submits blank or overlong text
- **THEN** validation explains the problem and the existing car remains unchanged

### Requirement: Safe concurrent car correction
Car correction SHALL verify the target is still the single active car and detect stale revisions. The UI SHALL preserve unsaved input and explain conflicts. No active car or multiple active cars SHALL produce an explicit unavailable/conflict state rather than choosing an arbitrary car.

#### Scenario: Two operator screens edit concurrently
- **WHEN** an operator saves against a revision superseded by another save
- **THEN** the API rejects the stale edit and returns current information without overwriting it

#### Scenario: No unique active car
- **WHEN** zero or multiple cars are active
- **THEN** manual correction is unavailable and the UI explains that the active-car context must be resolved
