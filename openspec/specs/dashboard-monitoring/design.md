# Dashboard and Monitoring Design

## Current implementation

- `src/kiosk/dashboard.py` is a Streamlit dashboard with local DB/API access, status cards, class breakdown, live video, event log, action controls, and a WebSocket client helper.
- `src/monitoring/metrics.py` defines Prometheus counters/gauges/histograms plus monitoring routes.
- `docker-compose.monitoring.yml` provides Prometheus and Grafana containers.
- Main Docker Compose routes dashboard access through nginx.
