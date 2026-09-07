# Deployment Specification

## Purpose

Define the supported local/edge deployment shape and durable resources required to run Bag Counter Edge without a cloud dependency.

## Requirements

### Requirement: On-premise operation
The system SHALL support running the counting stack on local edge hardware without requiring a cloud-hosted processing service.

#### Scenario: Edge host has local camera network access
- **WHEN** the application stack is deployed with its local dependencies and model artifact
- **THEN** frame processing, counting, persistence, dashboard/API access, and local evidence storage can operate on the edge host

### Requirement: Containerized multi-service deployment
The project SHALL provide a Docker Compose deployment that defines the application API/CV service and supporting local services needed by optional background, dashboard, proxy, and NVR functionality.

#### Scenario: Main Compose stack is started
- **WHEN** Docker Compose starts the main deployment
- **THEN** service definitions are available for Redis, edge-cv, Celery worker, Celery beat, nginx, dashboard, and NVR

### Requirement: Persistent local data mounts
The deployment SHALL keep database, logs, clips, and NVR media on persistent local storage mounts rather than relying solely on ephemeral container filesystems.

#### Scenario: Application container is recreated
- **WHEN** a service container is replaced while its host storage directory is retained
- **THEN** persisted application storage remains available to the new container

### Requirement: Model artifact injection
The edge CV service SHALL load model artifacts from a project/deployment model location that can be supplied independently of rebuilding application source.

#### Scenario: Model file is replaced in the mounted models directory
- **WHEN** configuration points to a compatible replacement artifact and the CV service is restarted
- **THEN** the detector initializes using the configured artifact without requiring source-code edits

### Requirement: Graceful application shutdown
The counting process SHALL respond to normal termination signals by stopping frame acquisition and completing/closing owned clip-processing resources.

#### Scenario: SIGINT or SIGTERM is received
- **WHEN** the pipeline is running
- **THEN** it exits the processing loop and executes its shutdown path
