## ADDED Requirements

### Requirement: Compact operator overview
The dashboard SHALL show a visually dominant current-car saved bag count, class totals, current car number, camera/detector/tracker status, last detection, recent saved events, a count graph and an alert summary without page scrolling at desktop viewports of at least 1366 by 768 CSS pixels at normal zoom. Smaller viewports SHALL retain access to all information through responsive layout or scrolling.

#### Scenario: Desktop loading overview
- **WHEN** an operator opens the dashboard at the target viewport
- **THEN** all overview elements are visible together and the current-car count is the largest numerical display
- **AND** longer history and expanded video are available on demand

#### Scenario: Intermediate desktop breakpoint
- **WHEN** the dashboard is displayed at 1500x950, 1920x950, or sizes immediately around the enlarged-layout breakpoint
- **THEN** the document does not require vertical scrolling and all required overview content remains visible
- **AND** the fix preserves the large count, readable cards and six visible recent events at 1920x1080, without hiding content or disabling document scrolling to mask overflow

### Requirement: Truthful counting status
The dashboard SHALL derive Online and Offline from counting-service telemetry, independently of browser connectivity. It SHALL distinguish model startup, stopped/faulted or stalled processing, missing camera frames, and unavailable status. A running model waiting for bags SHALL remain Online.

#### Scenario: Empty conveyor
- **WHEN** fresh frames are processed successfully but no bags are detected
- **THEN** counting is Online and the tracker is Running with no active bags

#### Scenario: Camera interruption
- **WHEN** the model service remains alive but fresh camera frames stop
- **THEN** camera status becomes unavailable and a prominent Counting interrupted warning appears
- **AND** the UI does not imply that bags are currently being processed

#### Scenario: Model stopped or processing stalled
- **WHEN** service telemetry expires or inference fails or stalls beyond the configured processing deadline
- **THEN** counting is Offline with the last known reason and update time

#### Scenario: Dashboard connection lost
- **WHEN** current telemetry cannot be obtained because the dashboard connection fails
- **THEN** the screen labels status unavailable and cached data stale instead of presenting a confirmed model shutdown

### Requirement: Local time and stable rendering
The dashboard SHALL display its clock, event times and graph labels in the viewing computer's local timezone. The browser title SHALL remain Bag Counter and live updates SHALL NOT reload the page, blink the title, reset input focus or discard unsaved car entry.

#### Scenario: Local timezone differs from server
- **WHEN** the viewing computer uses a different timezone from the server
- **THEN** the clock and event/chart timestamps consistently use the viewing computer's timezone

#### Scenario: Live updates during car entry
- **WHEN** new telemetry and events arrive while an operator types a number
- **THEN** input text and focus remain intact and the browser title remains stable

### Requirement: Separate detection from saved counts
The dashboard SHALL show the latest detected bag with observation time, available thumbnail and classification, and its known state. The latest selected observation SHALL be retained immediately, independently of publication/render throttling, and empty frames SHALL NOT erase it. Unknown classification and Unconfirmed tracking state SHALL be explicit and distinct. The main count and recent count list SHALL reflect committed events only.

#### Scenario: Detection has not been counted
- **WHEN** a bag is detected but no count event has committed
- **THEN** the latest detection is displayed without increasing the saved bag total

#### Scenario: No detection or unavailable thumbnail
- **WHEN** no detection exists or its image is unavailable
- **THEN** the card displays an explicit empty or image-unavailable state without fabricated data

#### Scenario: Detection visible for less than 500 ms
- **WHEN** an empty frame is followed by a detection at t=100 ms and an empty frame at t=600 ms, with no newer detection
- **THEN** the next successful publication/render shows the retained detection and its observation time
- **AND** saved counts remain unchanged until a BagEvent commits

#### Scenario: Candidate not yet confirmed
- **WHEN** the selected detection has no confirmed track reference
- **THEN** the card explicitly shows Unconfirmed, independently of whether its classification is known
- **AND** it does not imply a saved count or reuse another observation's thumbnail

### Requirement: Scoped count history
The dashboard SHALL display recent saved events and a graph of saved bags per minute scoped to the current car, defaulting to the last 30 minutes. Empty time buckets SHALL be zero and no-active-car state SHALL be explicit rather than silently substituting all-time totals.

#### Scenario: Current car has sparse events
- **WHEN** events exist in only some minutes of the selected interval
- **THEN** the graph contains zero buckets for other minutes and excludes events belonging to other cars

### Requirement: Operator-facing alerts
The dashboard SHALL show active camera, processing, persistence and communication errors or warnings in plain language with occurrence time and recovery state. Repeated instances SHALL be grouped. Communication and derived-status incidents SHALL retain bounded, timestamped active and recovered episode details for the current browser session; successful snapshots SHALL NOT erase that history. Recovery SHALL be tracked for the dependency that failed. Technical paths, credentials, stack traces and maintenance links SHALL NOT appear in the primary overview.

#### Scenario: Repeated camera failure and recovery
- **WHEN** the same camera error recurs and subsequently recovers
- **THEN** one grouped active warning is updated and then marked recovered without flooding the recent count list

#### Scenario: Communication failure and recovery
- **WHEN** communication fails and subsequently recovers
- **THEN** details show the incident's first/last occurrence, count, active/recovered state and recovery time
- **AND** recovered details remain available when the overview returns to No active warnings

#### Scenario: Repeated and subsequent outages
- **WHEN** the same failure is reported repeatedly during one outage and then occurs again after recovery
- **THEN** repeated reports are grouped into the active episode and the subsequent outage creates a new episode while retaining recovered context within the history bound

#### Scenario: Independent transport recovery
- **WHEN** fallback HTTP polling succeeds while the WebSocket or API-to-Redis connection remains unavailable
- **THEN** recovery of the working path does not incorrectly mark the still-failed dependency recovered
- **AND** saved counts remain based on authoritative snapshots and counting status remains independent of socket connectivity

#### Scenario: Bounded incident history
- **WHEN** more than 20 incident episodes are observed during a browser session
- **THEN** retained episode history remains bounded at 20, repeated active reports are coalesced, and oldest recovered episodes are evicted first
- **AND** the remaining active and recovered details retain their timestamps without entering the recent saved-count list
