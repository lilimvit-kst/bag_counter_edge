# Bag Classification Specification

## Purpose

Define the post-detection classification of a tracked bag into operational bag classes used for counting and reporting.

## Requirements

### Requirement: Supported operational classes
The system SHALL classify a counted track as exactly one of `empty`, `25kg`, or `50kg` based on its estimated volume.

#### Scenario: Estimated volume is below empty threshold
- **WHEN** estimated volume is less than the configured empty-volume maximum
- **THEN** the class is `empty`

#### Scenario: Estimated volume is within 25 kg range
- **WHEN** estimated volume is at least the empty threshold and no greater than the configured 25 kg maximum
- **THEN** the class is `25kg`

#### Scenario: Estimated volume exceeds 25 kg range
- **WHEN** estimated volume is greater than the configured 25 kg maximum
- **THEN** the class is `50kg`

### Requirement: Monocular volume estimate fallback
The system SHALL provide an estimated volume when no depth map is used so the counting pipeline can still classify bags in the current single-camera deployment.

#### Scenario: Depth estimation is disabled
- **WHEN** a bag detection has a valid bounding box and no depth map is supplied
- **THEN** the system calculates a non-depth proxy volume from the apparent bounding-box dimensions

### Requirement: Optional depth-based estimate
The system SHALL support an optional depth-based volume estimate when depth input is configured and available.

#### Scenario: Valid depth data is available
- **WHEN** depth mode is enabled and the detected bag region contains valid positive depth samples
- **THEN** the estimator returns a real-world volume estimate in liters based on the depth crop and camera geometry approximation
