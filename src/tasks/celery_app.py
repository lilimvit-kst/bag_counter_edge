"""
Celery application configuration for Bag Counter Edge.

Uses Redis as message broker and result backend.
"""
from celery import Celery
from src.config import settings

# Celery configuration
celery_app = Celery(
    'bag_counter',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=['src.tasks.tasks']
)

# Celery settings
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    task_soft_time_limit=240,  # 4 minutes soft limit
    worker_prefetch_multiplier=1,  # Fair task distribution
    worker_max_tasks_per_child=1000,  # Prevent memory leaks
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=5,
    broker_connection_retry_delay=2,
    
    # Result backend settings
    result_expires=3600,  # Expire results after 1 hour
    result_extended=True,  # Store additional task info
    
    # Rate limiting
    task_default_rate_limit='100/m',  # 100 tasks per minute
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)


def get_celery_app():
    """Get the Celery application instance."""
    return celery_app
