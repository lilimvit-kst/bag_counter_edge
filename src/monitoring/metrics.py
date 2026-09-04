"""
Prometheus metrics exporter for Bag Counter Edge.

Provides:
- /metrics endpoint for Prometheus scraping
- Custom metrics for bag counting, system health, performance
- Grafana-compatible metric names and labels
"""
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
)
from fastapi import Response, Request
from fastapi.routing import APIRouter
import time
from typing import Optional
from contextlib import contextmanager

# Create custom registry for application metrics
registry = CollectorRegistry()

# ── Metrics Definitions ──────────────────────────────────────────────────────

# Counter metrics
BAG_COUNT_TOTAL = Counter(
    'bag_counter_bags_total',
    'Total number of bags counted',
    ['class', 'wagon_id', 'shift_id'],
    registry=registry
)

DETECTION_ERRORS = Counter(
    'bag_counter_detection_errors_total',
    'Total number of detection errors',
    ['error_type'],
    registry=registry
)

API_REQUESTS_TOTAL = Counter(
    'bag_counter_api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status_code'],
    registry=registry
)

NOTIFICATIONS_SENT = Counter(
    'bag_counter_notifications_sent_total',
    'Total notifications sent',
    ['channel', 'type'],
    registry=registry
)

# Gauge metrics
ACTIVE_WAGON_GAUGE = Gauge(
    'bag_counter_active_wagon',
    'Current active wagon ID',
    registry=registry
)

ACTIVE_SHIFT_GAUGE = Gauge(
    'bag_counter_active_shift',
    'Current active shift ID',
    registry=registry
)

CONNECTED_CLIENTS_GAUGE = Gauge(
    'bag_counter_websocket_clients',
    'Number of connected WebSocket clients',
    registry=registry
)

CAMERA_STATUS_GAUGE = Gauge(
    'bag_counter_camera_status',
    'Camera connection status (1=connected, 0=disconnected)',
    ['camera_id'],
    registry=registry
)

SYSTEM_MEMORY_USAGE = Gauge(
    'bag_counter_memory_usage_bytes',
    'Current memory usage in bytes',
    registry=registry
)

SYSTEM_CPU_USAGE = Gauge(
    'bag_counter_cpu_usage_percent',
    'Current CPU usage percentage',
    registry=registry
)

DB_CONNECTIONS_ACTIVE = Gauge(
    'bag_counter_db_connections_active',
    'Number of active database connections',
    registry=registry
)

QUEUE_SIZE_GAUGE = Gauge(
    'bag_counter_celery_queue_size',
    'Current Celery task queue size',
    ['queue_name'],
    registry=registry
)

# Histogram metrics
PROCESSING_TIME_HISTOGRAM = Histogram(
    'bag_counter_processing_time_seconds',
    'Time spent processing frames',
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    registry=registry
)

API_LATENCY_HISTOGRAM = Histogram(
    'bag_counter_api_latency_seconds',
    'API request latency',
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    labels=['method', 'endpoint'],
    registry=registry
)

DETECTION_CONFIDENCE_HISTOGRAM = Histogram(
    'bag_counter_detection_confidence',
    'Detection confidence scores',
    buckets=[0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99],
    registry=registry
)

# Summary metrics
FRAME_PROCESSING_SUMMARY = Summary(
    'bag_counter_frame_processing_summary',
    'Frame processing time summary',
    registry=registry
)


# ── Helper Functions ─────────────────────────────────────────────────────────

def record_bag_detected(bag_class: str, wagon_id: Optional[int] = None, shift_id: Optional[int] = None):
    """Record a bag detection event."""
    BAG_COUNT_TOTAL.labels(
        bag_class=bag_class,
        wagon_id=wagon_id or 'unknown',
        shift_id=shift_id or 'unknown'
    ).inc()


def record_detection_confidence(confidence: float):
    """Record detection confidence score."""
    DETECTION_CONFIDENCE_HISTOGRAM.observe(confidence)


def record_detection_error(error_type: str):
    """Record a detection error."""
    DETECTION_ERRORS.labels(error_type=error_type).inc()


def record_api_request(method: str, endpoint: str, status_code: int, duration: float):
    """Record an API request with latency."""
    API_REQUESTS_TOTAL.labels(
        method=method,
        endpoint=endpoint,
        status_code=status_code
    ).inc()
    
    API_LATENCY_HISTOGRAM.labels(
        method=method,
        endpoint=endpoint
    ).observe(duration)


def record_notification_sent(channel: str, notification_type: str):
    """Record a notification being sent."""
    NOTIFICATIONS_SENT.labels(
        channel=channel,
        type=notification_type
    ).inc()


def update_system_metrics(memory_bytes: int, cpu_percent: float):
    """Update system resource metrics."""
    SYSTEM_MEMORY_USAGE.set(memory_bytes)
    SYSTEM_CPU_USAGE.set(cpu_percent)


def update_connected_clients(count: int):
    """Update connected WebSocket clients count."""
    CONNECTED_CLIENTS_GAUGE.set(count)


def update_camera_status(camera_id: str, is_connected: bool):
    """Update camera connection status."""
    CAMERA_STATUS_GAUGE.labels(camera_id=camera_id).set(1 if is_connected else 0)


def update_queue_size(queue_name: str, size: int):
    """Update Celery queue size."""
    QUEUE_SIZE_GAUGE.labels(queue_name=queue_name).set(size)


@contextmanager
def track_processing_time(metric_name: str = 'default'):
    """Context manager to track processing time."""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        PROCESSING_TIME_HISTOGRAM.observe(duration)
        FRAME_PROCESSING_SUMMARY.observe(duration)


# ── FastAPI Integration ──────────────────────────────────────────────────────

router = APIRouter()


@router.get("/metrics")
async def metrics_endpoint(request: Request):
    """
    Prometheus metrics endpoint.
    
    Returns all metrics in Prometheus text format.
    Compatible with Prometheus server and Grafana.
    """
    # Update dynamic metrics before exposing
    update_dynamic_metrics()
    
    # Generate metrics output
    metrics_data = generate_latest(registry)
    
    return Response(
        content=metrics_data,
        media_type=CONTENT_TYPE_LATEST
    )


@router.get("/health")
async def health_with_metrics():
    """
    Health check endpoint with basic metrics.
    
    Returns service health status along with key metrics.
    """
    return {
        "status": "healthy",
        "metrics_available": True,
        "prometheus_endpoint": "/metrics"
    }


def update_dynamic_metrics():
    """Update metrics that require runtime data."""
    # This function should be called periodically or before metrics exposure
    # to update metrics that depend on application state
    
    # Example: Update DB connections
    # from src.db.models import SessionLocal, Wagon, Shift
    # db = SessionLocal()
    # active_wagon = db.query(Wagon).filter_by(is_active=True).first()
    # if active_wagon:
    #     ACTIVE_WAGON_GAUGE.set(active_wagon.id)
    # active_shift = db.query(Shift).filter_by(is_active=True).first()
    # if active_shift:
    #     ACTIVE_SHIFT_GAUGE.set(active_shift.id)
    pass


# ── Grafana Dashboard Configuration ──────────────────────────────────────────

GRAFANA_DASHBOARD_JSON = {
    "dashboard": {
        "title": "Bag Counter Edge - Operations Dashboard",
        "tags": ["bag-counter", "operations"],
        "timezone": "browser",
        "panels": [
            {
                "title": "Total Bags Counted",
                "type": "stat",
                "targets": [
                    {
                        "expr": "sum(bag_counter_bags_total)",
                        "legendFormat": "Total Bags"
                    }
                ]
            },
            {
                "title": "Bags by Class",
                "type": "piechart",
                "targets": [
                    {
                        "expr": "sum by (class) (bag_counter_bags_total)",
                        "legendFormat": "{{class}}"
                    }
                ]
            },
            {
                "title": "Processing Time",
                "type": "histogram",
                "targets": [
                    {
                        "expr": "histogram_quantile(0.95, rate(bag_counter_processing_time_seconds_bucket[5m]))",
                        "legendFormat": "P95 Processing Time"
                    }
                ]
            },
            {
                "title": "API Latency",
                "type": "timeseries",
                "targets": [
                    {
                        "expr": "histogram_quantile(0.95, rate(bag_counter_api_latency_seconds_bucket[5m]))",
                        "legendFormat": "P95 API Latency"
                    }
                ]
            },
            {
                "title": "System Resources",
                "type": "timeseries",
                "targets": [
                    {
                        "expr": "bag_counter_cpu_usage_percent",
                        "legendFormat": "CPU Usage %"
                    },
                    {
                        "expr": "bag_counter_memory_usage_bytes / 1024 / 1024",
                        "legendFormat": "Memory Usage MB"
                    }
                ]
            },
            {
                "title": "WebSocket Clients",
                "type": "stat",
                "targets": [
                    {
                        "expr": "bag_counter_websocket_clients",
                        "legendFormat": "Connected Clients"
                    }
                ]
            },
            {
                "title": "Detection Errors",
                "type": "timeseries",
                "targets": [
                    {
                        "expr": "rate(bag_counter_detection_errors_total[5m])",
                        "legendFormat": "{{error_type}}"
                    }
                ]
            },
            {
                "title": "Queue Size",
                "type": "timeseries",
                "targets": [
                    {
                        "expr": "bag_counter_celery_queue_size",
                        "legendFormat": "{{queue_name}}"
                    }
                ]
            }
        ]
    }
}


@router.get("/grafana/dashboard")
async def grafana_dashboard():
    """Return pre-configured Grafana dashboard JSON."""
    return GRAFANA_DASHBOARD_JSON
