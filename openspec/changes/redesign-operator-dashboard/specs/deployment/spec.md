## ADDED Requirements

### Requirement: Local operator dashboard delivery
The deployment SHALL serve the operator dashboard and its API, live updates and video through one local origin without requiring internet assets. Existing persisted events and legacy read API routes SHALL remain accessible during rollout.

#### Scenario: Offline local network
- **WHEN** the edge host and camera are reachable but internet access is absent
- **THEN** dashboard layout, chart, login and live data operate using locally served resources

### Requirement: Correct service roles
The deployment SHALL launch one intended counting process for the configured source and execute Celery worker and beat commands as their respective service roles.

#### Scenario: Main stack starts
- **WHEN** the provided stack is started
- **THEN** worker and beat do not launch additional counting pipelines and dashboard live traffic reaches the API service

### Requirement: Operator credential environment mapping
The main, 2CPU and 4CPU Compose variants SHALL consistently supply operator credentials through the application's API_ADMIN_USER and API_ADMIN_PASS settings. Existing ADMIN_USERNAME and ADMIN_PASSWORD inputs SHALL map to those canonical names, with explicitly configured canonical values taking precedence. The mapping SHALL preserve existing HTTP/JWT contracts and SHALL NOT require changes to real secrets or unrelated configuration aliases.

#### Scenario: Legacy deployment credential names
- **WHEN** an installation supplies ADMIN_USERNAME and ADMIN_PASSWORD without canonical overrides
- **THEN** each provided Compose variant passes those configured values into API_ADMIN_USER and API_ADMIN_PASS and the operator can authenticate with them

#### Scenario: Canonical deployment credential names
- **WHEN** an installation supplies API_ADMIN_USER and API_ADMIN_PASS
- **THEN** those values define the operator account, including when conflicting legacy inputs are also present
- **AND** the same precedence is documented and tested through Settings initialization and actual login requests
