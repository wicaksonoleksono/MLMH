import atexit
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from flask import current_app

logger = logging.getLogger(__name__)

class SchedulerService:
    """Service for managing background scheduled tasks using APScheduler"""
    
    def __init__(self):
        self.scheduler = None
        self._jobs_registered = False
    
    def init_scheduler(self, app):
        """Initialize and start APScheduler with Flask app context"""
        if self.scheduler is not None:
            logger.info("APScheduler already initialized, skipping...")
            return

        # Create BackgroundScheduler with timezone and executor configuration
        timezone = app.config.get('SCHEDULER_TIMEZONE', 'Asia/Jakarta')
        executors = {
            'default': {
                'type': 'threadpool',
                'max_workers': 5  # Allow up to 5 concurrent tasks (but each facial analysis job has max_instances=1)
            }
        }
        job_defaults = {
            'coalesce': True,  # Combine multiple pending jobs
            'max_instances': 1  # Prevent duplicate execution
        }
        self.scheduler = BackgroundScheduler(
            timezone=timezone,
            executors=executors,
            job_defaults=job_defaults
        )
        
        # Add scheduled jobs with Flask app context
        with app.app_context():
            self._register_jobs(app)
        
        try:
            # Start scheduler
            self.scheduler.start()
            logger.info(f"APScheduler started successfully with timezone: {timezone}")
            
            # Register graceful shutdown
            atexit.register(self._shutdown_scheduler)
            
        except Exception as e:
            logger.error(f"Failed to start APScheduler: {e}")
            raise
    
    def _register_jobs(self, app):
        """Register all scheduled jobs"""
        if self._jobs_registered:
            return

        # Job 1: OTP Cleanup - Process scheduled deletions hourly
        self._add_otp_cleanup_job(app)

        # Job 2: SESMAN Notifications - Daily at specified hour
        self._add_sesman_notification_job(app)

        # Job 3: Facial Analysis Task Cleanup - Daily cleanup of old task history
        self._add_facial_analysis_cleanup_job(app)

        # Job 4: Facial Analysis Queue Processor - Process facial analysis tasks sequentially (every 5 seconds)
        self._add_facial_analysis_queue_processor_job(app)

        self._jobs_registered = True
        logger.info("All scheduled jobs registered successfully")
    
    def _add_otp_cleanup_job(self, app):
        """Add hourly job to process scheduled user deletions"""
        interval_hours = app.config.get('OTP_CLEANUP_INTERVAL_HOURS', 1)
        
        self.scheduler.add_job(
            func=self._execute_otp_cleanup,
            trigger=IntervalTrigger(hours=interval_hours),
            id='otp_scheduled_cleanup',
            name='OTP Scheduled Cleanup Job',
            replace_existing=True,
            max_instances=1,  # Prevent overlapping executions
            misfire_grace_time=300,  # 5 minutes grace time
            kwargs={'app': app}
        )
        logger.info(f"OTP cleanup job scheduled every {interval_hours} hour(s)")
    
    def _add_sesman_notification_job(self, app):
        """Add daily job for Session 2 notifications"""
        notification_hour = app.config.get('SESMAN_NOTIFICATION_HOUR', 9)

        self.scheduler.add_job(
            func=self._execute_sesman_notifications,
            trigger=CronTrigger(hour=notification_hour, minute=0),
            id='sesman_daily_notifications',
            name='SESMAN Daily Notifications Job',
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=1800,  # 30 minutes grace time
            kwargs={'app': app}
        )
        logger.info(f"SESMAN notification job scheduled daily at {notification_hour}:00")

    def _add_facial_analysis_cleanup_job(self, app):
        """Add daily job to cleanup old facial analysis task history"""
        self.scheduler.add_job(
            func=self._execute_facial_analysis_cleanup,
            trigger=CronTrigger(hour=2, minute=0),  # 2 AM daily
            id='facial_analysis_task_cleanup',
            name='Facial Analysis Task Cleanup Job',
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=3600,  # 1 hour grace time
            kwargs={'app': app}
        )
        logger.info("Facial analysis task cleanup job scheduled daily at 02:00")

    def _add_facial_analysis_queue_processor_job(self, app):
        """Add high-frequency job to process facial analysis tasks from queue sequentially"""
        from apscheduler.triggers.interval import IntervalTrigger

        self.scheduler.add_job(
            func=self._execute_facial_analysis_queue_processor,
            trigger=IntervalTrigger(seconds=5),  # Check queue every 5 seconds
            id='facial_analysis_queue_processor',
            name='Facial Analysis Queue Processor',
            replace_existing=True,
            max_instances=1,  # Ensure only one processor runs at a time
            misfire_grace_time=10,
            kwargs={'app': app}
        )
        logger.info("Facial analysis queue processor scheduled to run every 5 seconds")

    def _execute_facial_analysis_queue_processor(self, app):
        """Execute the facial analysis task queue processor - processes one task at a time sequentially"""
        with app.app_context():
            try:
                from .facial_analysis.backgroundProcessingService import FacialAnalysisBackgroundService

                # Process one task from the queue
                FacialAnalysisBackgroundService.process_queue()

            except Exception as e:
                logger.error(f"Facial analysis queue processor failed: {e}")
                # Don't re-raise to prevent scheduler from stopping

    def _execute_otp_cleanup(self, app):
        """Execute OTP cleanup task within Flask app context"""
        with app.app_context():
            try:
                logger.info("Starting scheduled OTP cleanup task...")
                
                from .shared.emailOTPService import EmailOTPService
                from ..model.shared.users import User
                from ..db import get_session
                
                # Process users scheduled for deletion
                with get_session() as db:
                    # Find users scheduled for deletion
                    now = datetime.utcnow()
                    users_to_delete = db.query(User).filter(
                        User.deletion_scheduled_at <= now,
                        User.email_verified == False,
                        User.deletion_scheduled_at.isnot(None)
                    ).all()
                    
                    deleted_count = 0
                    for user in users_to_delete:
                        logger.info(f"Deleting unverified user: {user.uname} (scheduled at {user.deletion_scheduled_at})")
                        db.delete(user)
                        deleted_count += 1
                    
                    db.commit()
                    
                    if deleted_count > 0:
                        logger.info(f"OTP cleanup completed: {deleted_count} unverified users deleted")
                    else:
                        logger.info("OTP cleanup completed: No users scheduled for deletion")
                    
                    return {
                        'deleted_users': deleted_count,
                        'cleaned_otps': 0  # We delete users entirely, not just clean OTPs
                    }
                        
            except Exception as e:
                logger.error(f"OTP cleanup task failed: {e}")
                # Don't re-raise to prevent scheduler from stopping
                return {
                    'deleted_users': 0,
                    'cleaned_otps': 0,
                    'error': str(e)
                }
    
    def _execute_sesman_notifications(self, app):
        """Execute SESMAN notification task within Flask app context"""
        with app.app_context():
            try:
                logger.info("Starting SESMAN notification task...")

                from .SMTP.session2NotificationService import Session2NotificationService

                # Create automatic notifications for eligible users (14+ days after Session 1)
                # This creates notification records in the database
                created_count = Session2NotificationService.create_automatic_notifications()

                if created_count > 0:
                    logger.info(f"Created {created_count} automatic notification records")

                    # Now send the pending notifications
                    sent_count = Session2NotificationService.send_pending_notifications()

                    logger.info(f"SESMAN notifications completed: {sent_count} notifications sent successfully")
                    return {
                        'notifications_created': created_count,
                        'notifications_sent': sent_count
                    }
                else:
                    logger.info("No new users eligible for Session 2 notification today")

                    # Still try to send any existing pending notifications
                    sent_count = Session2NotificationService.send_pending_notifications()
                    if sent_count > 0:
                        logger.info(f"Sent {sent_count} existing pending notifications")

                    return {
                        'notifications_created': 0,
                        'notifications_sent': sent_count
                    }

            except Exception as e:
                logger.error(f"SESMAN notification task failed: {e}")
                import traceback
                traceback.print_exc()
                # Don't re-raise to prevent scheduler from stopping
                return {
                    'notifications_created': 0,
                    'notifications_sent': 0,
                    'error': str(e)
                }
    
    def _execute_facial_analysis_cleanup(self, app):
        """Execute facial analysis task cleanup within Flask app context"""
        with app.app_context():
            try:
                logger.info("Starting facial analysis task cleanup...")

                from .facial_analysis.backgroundProcessingService import FacialAnalysisBackgroundService

                # Clean up tasks older than 7 days
                removed_count = FacialAnalysisBackgroundService.clean_old_tasks(days=7)

                logger.info(f"Facial analysis cleanup completed: {removed_count} old tasks removed")
                return {'removed_tasks': removed_count}

            except Exception as e:
                logger.error(f"Facial analysis cleanup task failed: {e}")
                # Don't re-raise to prevent scheduler from stopping
                return {'removed_tasks': 0, 'error': str(e)}

    def _shutdown_scheduler(self):
        """Gracefully shutdown the scheduler"""
        if self.scheduler and self.scheduler.running:
            logger.info("Shutting down APScheduler...")
            self.scheduler.shutdown(wait=False)
            logger.info("APScheduler shut down successfully")
    
    def get_job_status(self):
        """Get current status of all scheduled jobs"""
        if not self.scheduler:
            return {"status": "not_initialized", "jobs": []}
        
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "func": job.func.__name__ if hasattr(job.func, '__name__') else str(job.func)
            })
        
        return {
            "status": "running" if self.scheduler.running else "stopped",
            "timezone": str(self.scheduler.timezone),
            "jobs": jobs
        }

# Global scheduler service instance
scheduler_service = SchedulerService()

def init_scheduler(app):
    """Initialize the global scheduler service with Flask app"""
    scheduler_service.init_scheduler(app)

def get_scheduler_status():
    """Get current scheduler status and job information"""
    return scheduler_service.get_job_status()