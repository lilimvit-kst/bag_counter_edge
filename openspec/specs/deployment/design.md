# Deployment Design

## Current implementation

Main `docker-compose.yml` services:

- `redis` — Celery broker/result support;
- `edge-cv` — main image exposing FastAPI and configured application runtime;
- `celery-worker` — background task execution;
- `celery-beat` — periodic scheduling;
- `nginx` — reverse proxy;
- `dashboard` — Streamlit UI;
- `nvr` — FFmpeg RTSP segment recording.

`docker-compose-2CPU.yml` and `docker-compose-4CPU.yml` provide alternative resource-oriented deployment variants. Monitoring is split into `docker-compose.monitoring.yml`.

The main compose currently requests NVIDIA GPU access for `edge-cv`, but runtime detector inference is still forced to CPU. Treat hardware acceleration as unresolved until explicitly changed.
