"""
Celery tasks for Bag Counter Edge.

All long-running or I/O-bound operations should be offloaded to Celery workers.
"""
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from celery import Task
from loguru import logger

from src.tasks.celery_app import celery_app
from src.config import settings
from src.notifications.notifier import NotificationService, WagonReport


class BaseTask(Task):
    """Base task with common error handling and logging."""
    
    _abstract = True
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Log task failures."""
        logger.error(
            f"Task {self.name} (id={task_id}) failed: {exc}\n"
            f"Args: {args}, Kwargs: {kwargs}\n"
            f"Traceback: {einfo.traceback}"
        )
    
    def on_success(self, retval, task_id, args, kwargs):
        """Log task successes."""
        logger.debug(f"Task {self.name} (id={task_id}) completed successfully")


@celery_app.task(base=BaseTask, bind=True, max_retries=3)
def process_clip_task(
    self,
    timestamp: float,
    event_id: Optional[int] = None,
    track_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Process and save video clip for an event.
    
    Args:
        timestamp: Unix timestamp of the event
        event_id: Database event ID (optional)
        track_id: Track ID for naming (optional)
    
    Returns:
        Dict with clip path and status
    """
    try:
        logger.info(f"Processing clip for timestamp={timestamp}, track_id={track_id}")
        
        # Import here to avoid circular imports
        from src.nvr.clip_recorder import ClipRecorder
        
        recorder = ClipRecorder()
        clip_path = recorder._extract_clip(timestamp)  # Use internal method
        
        if clip_path and Path(clip_path).exists():
            logger.success(f"Clip saved: {clip_path}")
            return {
                "status": "success",
                "clip_path": str(clip_path),
                "timestamp": timestamp,
                "event_id": event_id,
                "track_id": track_id,
            }
        else:
            logger.warning(f"Clip extraction returned no file for timestamp={timestamp}")
            return {
                "status": "no_clip",
                "clip_path": None,
                "timestamp": timestamp,
                "reason": "No clip extracted",
            }
            
    except Exception as exc:
        logger.error(f"Clip processing failed: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery_app.task(base=BaseTask, bind=True, max_retries=3)
def send_notification_task(
    self,
    event_type: str,
    data: Dict[str, Any],
    channels: Optional[list] = None
) -> Dict[str, Any]:
    """
    Send notification via configured channels.
    
    Args:
        event_type: Type of event (wagon_closed, low_stock, camera_error, etc.)
        data: Event data payload (should contain wagon_id for wagon_closed events)
        channels: List of channels to use (['email', 'telegram']), defaults to all enabled
    
    Returns:
        Dict with delivery status for each channel
    """
    try:
        logger.info(f"Sending notification: {event_type}")
        
        notifier = NotificationService()
        results = {}
        
        # For wagon_closed events, build report from data
        if event_type == "wagon_closed" and data.get("wagon_id"):
            from sqlalchemy.orm import Session
            from src.notifications.notifier import build_report_from_wagon
            from src.db.models import SessionLocal
            
            db = SessionLocal()
            try:
                report = build_report_from_wagon(data["wagon_id"], db)
                if not report:
                    logger.warning(f"Wagon {data['wagon_id']} not found for notification")
                    return {"status": "error", "message": "Wagon not found"}
                
                # Determine which channels to use
                if channels is None:
                    channels = []
                    if settings.SMTP_HOST and settings.EMAIL_TO:
                        channels.append('email')
                    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
                        channels.append('telegram')
                
                for channel in channels:
                    try:
                        if channel == 'email':
                            success = notifier.send_email(report)
                            results['email'] = 'sent' if success else 'failed'
                        elif channel == 'telegram':
                            success = notifier.send_telegram(report)
                            results['telegram'] = 'sent' if success else 'failed'
                    except Exception as e:
                        logger.error(f"Notification via {channel} failed: {e}")
                        results[channel] = f'error: {str(e)}'
            finally:
                db.close()
        else:
            # Generic notification handling for other event types
            if channels is None:
                channels = []
                if settings.SMTP_HOST and settings.EMAIL_TO:
                    channels.append('email')
                if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
                    channels.append('telegram')
            
            # For non-wagon events, create simple WagonReport object
            for channel in channels:
                try:
                    simple_report = WagonReport(
                        wagon_number=data.get("wagon_number", "N/A"),
                        shift_operator=data.get("operator", "system"),
                        started_at=datetime.now(timezone.utc),
                        ended_at=datetime.now(timezone.utc),
                        total_bags=data.get("total_bags", 0),
                        bags_25kg=data.get("bags_25kg", 0),
                        bags_50kg=data.get("bags_50kg", 0),
                        empty_bags=data.get("empty_bags", 0),
                        total_weight_kg=data.get("weight_kg", 0),
                        avg_volume_liters=data.get("avg_volume", 0.0),
                        top_clip_paths=data.get("clip_paths", [])
                    )
                    if channel == 'email':
                        success = notifier.send_email(simple_report)
                        results['email'] = 'sent' if success else 'failed'
                    elif channel == 'telegram':
                        success = notifier.send_telegram(simple_report)
                        results['telegram'] = 'sent' if success else 'failed'
                except Exception as e:
                    logger.error(f"Notification via {channel} failed: {e}")
                    results[channel] = f'error: {str(e)}'
        
        logger.info(f"Notification results: {results}")
        return {
            "status": "completed",
            "event_type": event_type,
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
    except Exception as exc:
        logger.error(f"Notification task failed: {exc}")
        raise self.retry(exc=exc, countdown=5 * (self.request.retries + 1))


@celery_app.task(base=BaseTask, bind=True)
def generate_report_task(
    self,
    wagon_id: int,
    shift_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Generate comprehensive report for a wagon/shift.
    
    Args:
        wagon_id: Wagon database ID
        shift_id: Shift database ID (optional)
    
    Returns:
        Dict with report data
    """
    try:
        logger.info(f"Generating report for wagon_id={wagon_id}")
        
        from sqlalchemy.orm import Session
        from src.db.models import SessionLocal, Wagon, BagEvent, BagClass
        
        db = SessionLocal()
        try:
            wagon = db.query(Wagon).filter_by(id=wagon_id).first()
            if not wagon:
                return {"status": "error", "message": "Wagon not found"}
            
            # Query events for this wagon
            query = db.query(BagEvent).filter_by(wagon_id=wagon_id)
            total_count = query.count()
            
            by_class = {}
            for cls in BagClass:
                count = query.filter_by(bag_class=cls).count()
                by_class[cls.value] = count
            
            # Calculate weight
            weight_25 = by_class.get("25kg", 0) * 25
            weight_50 = by_class.get("50kg", 0) * 50
            total_weight_kg = weight_25 + weight_50
            
            report = WagonReport(
                wagon_id=wagon.wagon_number,
                total_bags=total_count,
                bags_25kg=by_class.get("25kg", 0),
                bags_50kg=by_class.get("50kg", 0),
                empty_bags=by_class.get("empty", 0),
                estimated_weight_tons=round(total_weight_kg / 1000.0, 2),
                started_at=wagon.started_at.isoformat() if wagon.started_at else None,
                ended_at=wagon.ended_at.isoformat() if wagon.ended_at else None,
            )
            
            logger.success(f"Report generated: {total_count} bags, {total_weight_kg}kg")
            
            return {
                "status": "success",
                "report": report.dict(),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            db.close()
            
    except Exception as exc:
        logger.error(f"Report generation failed: {exc}")
        raise self.retry(exc=exc, countdown=5)


@celery_app.task(base=BaseTask, bind=True)
def update_dashboard_task(
    self,
    wagon_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Update dashboard statistics (can be triggered periodically).
    
    Args:
        wagon_id: Specific wagon to update (optional, defaults to active)
    
    Returns:
        Dict with updated stats
    """
    try:
        from sqlalchemy.orm import Session
        from src.db.models import SessionLocal, Wagon, BagEvent, BagClass
        
        db = SessionLocal()
        try:
            if wagon_id:
                wagon = db.query(Wagon).filter_by(id=wagon_id).first()
            else:
                wagon = db.query(Wagon).filter_by(is_active=True).first()
            
            if not wagon:
                return {"status": "no_wagon", "message": "No active wagon"}
            
            stats_query = db.query(BagEvent).filter_by(wagon_id=wagon.id)
            total = stats_query.count()
            
            by_class = {}
            for cls in BagClass:
                by_class[cls.value] = stats_query.filter_by(bag_class=cls).count()
            
            weight_25 = by_class.get("25kg", 0) * 25
            weight_50 = by_class.get("50kg", 0) * 50
            
            return {
                "status": "success",
                "wagon_number": wagon.wagon_number,
                "total_bags": total,
                "by_class": by_class,
                "total_weight_kg": weight_25 + weight_50,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            db.close()
            
    except Exception as exc:
        logger.error(f"Dashboard update failed: {exc}")
        return {"status": "error", "message": str(exc)}


@celery_app.task(base=BaseTask, bind=True)
def cleanup_old_clips_task(self, retention_days: int = 7) -> Dict[str, Any]:
    """
    Clean up old video clips beyond retention period.
    
    Args:
        retention_days: Number of days to retain clips
    
    Returns:
        Dict with cleanup statistics
    """
    try:
        import shutil
        from datetime import timedelta
        
        cutoff_time = datetime.now() - timedelta(days=retention_days)
        clips_dir = settings.CLIPS_DIR
        
        if not clips_dir.exists():
            return {"status": "no_directory", "message": "Clips directory not found"}
        
        deleted_count = 0
        total_size_freed = 0
        
        for clip_file in clips_dir.glob("*.mp4"):
            try:
                file_mtime = datetime.fromtimestamp(clip_file.stat().st_mtime)
                if file_mtime < cutoff_time:
                    file_size = clip_file.stat().st_size
                    clip_file.unlink()
                    deleted_count += 1
                    total_size_freed += file_size
            except Exception as e:
                logger.error(f"Failed to delete {clip_file}: {e}")
        
        logger.info(
            f"Cleanup complete: deleted {deleted_count} clips, "
            f"freed {total_size_freed / (1024*1024):.2f} MB"
        )
        
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "total_size_freed_bytes": total_size_freed,
            "retention_days": retention_days,
        }
        
    except Exception as exc:
        logger.error(f"Cleanup task failed: {exc}")
        return {"status": "error", "message": str(exc)}
