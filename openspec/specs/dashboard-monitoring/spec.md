# Dashboard and Monitoring Specification

## Purpose

Define local operator visibility into counting state, recent events, video, service health, and runtime metrics.

## Requirements

### Requirement: Operator dashboard visibility
The system SHALL provide an operator dashboard that can display current counting status, class breakdown, recent events, and live video when those data sources are reachable.

#### Scenario: Dashboard has access to active data sources
- **WHEN** an operator opens the dashboard
- **THEN** current status metrics and recent event information are presented
- **AND** the live video component can use the configured API/video source

### Requirement: Realtime dashboard updates
The dashboard SHALL support realtime updates for current operational state and counting events.

#### Scenario: Dashboard receives a stats update
- **WHEN** a subscribed dashboard client receives a stats broadcast
- **THEN** the client can update its displayed statistics without requiring a full application restart

### Requirement: Prometheus-compatible metrics
The service SHALL expose runtime metrics in a format consumable by Prometheus.

#### Scenario: Monitoring system scrapes metrics
- **WHEN** Prometheus requests the configured metrics endpoint
- **THEN** the service returns current application/process metrics in Prometheus-compatible form

### Requirement: Monitoring deployment support
The deployment SHALL support optional monitoring components when monitoring is enabled in configuration.

#### Scenario: Monitoring compose stack is started
- **WHEN** the monitoring deployment definition is enabled
- **THEN** Prometheus can scrape configured application metrics and Grafana can use the monitoring data source
