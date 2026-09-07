# Bag Detection Specification

## Purpose

Define the detector contract that converts an input frame into candidate flour-bag detections for downstream tracking and counting.

## Requirements

### Requirement: Bag detection output
The system SHALL produce zero or more bag detections for each processed frame, where each detection contains a pixel bounding box, confidence score, and detector class identifier.

#### Scenario: Model finds a configured bag class
- **WHEN** the detector model reports an object whose class identifier is configured as a bag class and whose score survives model thresholds
- **THEN** the system returns that object as a bag detection

#### Scenario: Model finds a non-bag class
- **WHEN** the model reports an object whose class identifier is not configured as a bag class
- **THEN** the system excludes that object from downstream bag tracking

### Requirement: Configurable confidence and overlap thresholds
The system SHALL apply configured detection confidence and IoU thresholds during model inference.

#### Scenario: Threshold settings change
- **GIVEN** valid threshold configuration is supplied before startup
- **WHEN** the detector is initialized
- **THEN** subsequent inference uses those configured threshold values

### Requirement: Empty detection result is valid
The system SHALL treat a frame with no qualifying detections as a normal result rather than an application error.

#### Scenario: No bags are visible
- **WHEN** no model result qualifies as a configured bag detection
- **THEN** the detector returns an empty detection collection
