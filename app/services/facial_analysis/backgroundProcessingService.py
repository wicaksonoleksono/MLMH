"""
Background Processing Service for Facial Analysis

Handles queuing and executing facial analysis tasks asynchronously using APScheduler.
Prevents 504 timeouts by processing images in the background.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
from ...db import get_session
from ...model.assessment.facial_analysis import SessionFacialAnalysis
from .processingService import FacialAnalysisProcessingService

logger = logging.getLogger(__name__)


class FacialAnalysisBackgroundService:
    """Service for managing facial analysis background processing tasks"""

    # Store for tracking queued and active tasks
    _task_queue: Dict[str, Dict[str, Any]] = {}
    _active_tasks: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def queue_processing_task(
        cls,
        session_id: str,
        assessment_type: str,
        media_save_path: Optional[str] = None,
        scheduler=None
    ) -> Dict[str, Any]:
        """
        Queue a facial analysis processing task by creating a database record.
        The queue processor will pick it up and process it sequentially.

        Args:
            session_id: Assessment session ID
            assessment_type: 'PHQ' or 'LLM'
            media_save_path: Base path for media files (unused, kept for compatibility)
            scheduler: APScheduler instance (unused, kept for compatibility)

        Returns:
            {
                'success': bool,
                'message': str,
                'task_id': str,
                'status': 'queued'|'already_processing'|'already_completed'
            }
        """
        task_id = f"{session_id}_{assessment_type}"

        # Check if already processing or completed
        with get_session() as db:
            analysis = db.query(SessionFacialAnalysis).filter_by(
                session_id=session_id,
                assessment_type=assessment_type
            ).first()

            if analysis:
                if analysis.status == 'processing':
                    return {
                        'success': False,
                        'message': f'{assessment_type} analysis already being processed',
                        'task_id': task_id,
                        'status': 'already_processing'
                    }
                elif analysis.status == 'completed':
                    return {
                        'success': False,
                        'message': f'{assessment_type} analysis already completed',
                        'task_id': task_id,
                        'status': 'already_completed',
                        'analysis_id': analysis.id
                    }
                elif analysis.status == 'queued':
                    return {
                        'success': False,
                        'message': f'{assessment_type} analysis already queued',
                        'task_id': task_id,
                        'status': 'already_queued'
                    }

            # Create database record with status='queued'
            # Generate JSONL path (will be created during processing)
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            jsonl_filename = f"session_{session_id[:8]}_{assessment_type}_{timestamp}.jsonl"
            jsonl_path = f"facial_analysis/{jsonl_filename}"

            # Create new analysis record in database
            new_analysis = SessionFacialAnalysis(
                session_id=session_id,
                assessment_type=assessment_type,
                jsonl_file_path=jsonl_path,
                status='queued',
                total_images_processed=0,
                images_with_faces_detected=0,
                images_failed=0
            )
            db.add(new_analysis)
            db.commit()

            logger.info(f"[QUEUE] Created database record for task: {task_id}")

        return {
            'success': True,
            'message': f'{assessment_type} processing queued in database',
            'task_id': task_id,
            'status': 'queued'
        }

    @classmethod
    def _execute_processing_task(
        cls,
        session_id: str,
        assessment_type: str,
        media_save_path: Optional[str]
    ):
        """
        Execute facial analysis processing task (runs in background)

        Args:
            session_id: Assessment session ID
            assessment_type: 'PHQ' or 'LLM'
            media_save_path: Base path for media files
        """
        task_id = f"{session_id}_{assessment_type}"

        try:
            logger.info(f"Starting background processing task: {task_id}")
            cls._active_tasks[task_id] = {
                'status': 'processing',
                'started_at': datetime.utcnow(),
                'progress': 0
            }

            # Call the synchronous processing service
            result = FacialAnalysisProcessingService.process_session_assessment(
                session_id=session_id,
                assessment_type=assessment_type,
                media_save_path=media_save_path
            )

            cls._active_tasks[task_id]['status'] = 'completed'
            cls._active_tasks[task_id]['result'] = result.model_dump()
            cls._active_tasks[task_id]['completed_at'] = datetime.utcnow()

            logger.info(f"Completed background processing task: {task_id}")

        except Exception as e:
            logger.error(f"Background processing task failed: {task_id} - {str(e)}")
            cls._active_tasks[task_id]['status'] = 'failed'
            cls._active_tasks[task_id]['error'] = str(e)
            cls._active_tasks[task_id]['completed_at'] = datetime.utcnow()

    @classmethod
    def get_task_status(cls, session_id: str, assessment_type: str) -> Dict[str, Any]:
        """
        Get status of a facial analysis processing task

        Args:
            session_id: Assessment session ID
            assessment_type: 'PHQ' or 'LLM'

        Returns:
            {
                'task_id': str,
                'status': 'queued'|'processing'|'completed'|'failed'|'not_found',
                'progress': int (0-100),
                'started_at': str (ISO format),
                'completed_at': str (ISO format),
                'result': dict or None,
                'error': str or None
            }
        """
        task_id = f"{session_id}_{assessment_type}"

        # Check in-memory task tracking
        if task_id in cls._active_tasks:
            task_info = cls._active_tasks[task_id].copy()
            task_info['task_id'] = task_id

            # Convert datetime objects to ISO format strings
            if 'started_at' in task_info and task_info['started_at']:
                task_info['started_at'] = task_info['started_at'].isoformat()
            if 'completed_at' in task_info and task_info['completed_at']:
                task_info['completed_at'] = task_info['completed_at'].isoformat()

            return task_info

        # Check database for completed analysis
        with get_session() as db:
            analysis = db.query(SessionFacialAnalysis).filter_by(
                session_id=session_id,
                assessment_type=assessment_type
            ).first()

            if analysis:
                return {
                    'task_id': task_id,
                    'status': analysis.status,
                    'progress': 100 if analysis.status == 'completed' else 0,
                    'started_at': analysis.started_at.isoformat() if analysis.started_at else None,
                    'completed_at': analysis.completed_at.isoformat() if analysis.completed_at else None,
                    'analysis_id': analysis.id,
                    'error': analysis.error_message
                }

        return {
            'task_id': task_id,
            'status': 'not_found',
            'message': 'No processing task found for this session'
        }

    @classmethod
    def clean_old_tasks(cls, days: int = 7):
        """
        Clean up old completed/failed tasks from memory

        Args:
            days: Number of days to keep task history
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        tasks_to_remove = []

        for task_id, task_info in cls._active_tasks.items():
            if task_info.get('completed_at'):
                if task_info['completed_at'] < cutoff_time:
                    tasks_to_remove.append(task_id)

        for task_id in tasks_to_remove:
            del cls._active_tasks[task_id]
            logger.info(f"Cleaned old task: {task_id}")

        return len(tasks_to_remove)

    @classmethod
    def process_queue(cls):
        """
        Process the task queue using I/O overseer pattern (called by scheduler every 10 seconds).

        Acts as a "hook" that:
        - Exits immediately if queue is empty (no wasted resources)
        - Processes ONE session at a time (sequential)
        - Uses async/context-switching to send images to gRPC
        - Keeps all 4 gRPC workers busy with concurrent image requests
        - WSGI worker acts as I/O coordinator (non-blocking)

        Architecture:
        - 1 WSGI worker oversees the I/O (network requests to gRPC)
        - Each session sends images with controlled concurrency
        - gRPC server (4 workers) does ML computation (CPU-intensive)
        - Context switches while waiting for RPC responses

        Returns:
            {
                'processed': int - number of tasks processed (0 or 1)
                'task_id': str - the task that was processed (if any)
                'queue_size': int - remaining tasks in queue
            }
        """
        from ...db import get_session

        with get_session() as db:
            # Get ONE pending task (sequential processing)
            pending_task = db.query(SessionFacialAnalysis).filter_by(
                status='queued'
            ).first()

            if not pending_task:
                # No pending tasks - exit early (queue is empty)
                return {
                    'processed': 0,
                    'task_id': None,
                    'queue_size': 0
                }

            # Mark as processing
            task_id = f"{pending_task.session_id}_{pending_task.assessment_type}"
            pending_task.status = 'processing'
            session_id = pending_task.session_id
            assessment_type = pending_task.assessment_type
            db.commit()

            logger.info(f"[QUEUE-PROCESSOR] Starting task: {task_id}")

        # Process task (outside db session to avoid locks)
        try:
            # Execute the processing
            # This uses ThreadPoolExecutor(max_workers=4) internally
            # which sends 4 concurrent RPC requests, fully utilizing gRPC's 4 workers
            result = FacialAnalysisProcessingService.process_session_assessment(
                session_id=session_id,
                assessment_type=assessment_type,
                media_save_path=None  # Will be fetched from config
            )
            logger.info(f"[QUEUE-PROCESSOR] Completed task: {task_id}")

            # Get remaining queue size
            with get_session() as db:
                remaining = db.query(SessionFacialAnalysis).filter_by(status='queued').count()

            return {
                'processed': 1,
                'task_id': task_id,
                'queue_size': remaining
            }

        except Exception as e:
            logger.error(f"[QUEUE-PROCESSOR] Failed task {task_id}: {str(e)}")
            # Update status to failed
            with get_session() as db:
                failed_task = db.query(SessionFacialAnalysis).filter_by(
                    session_id=session_id,
                    assessment_type=assessment_type
                ).first()
                if failed_task:
                    failed_task.status = 'failed'
                    failed_task.error_message = str(e)
                    db.commit()

            # Get remaining queue size
            with get_session() as db:
                remaining = db.query(SessionFacialAnalysis).filter_by(status='queued').count()

            return {
                'processed': 0,
                'task_id': task_id,
                'error': str(e),
                'queue_size': remaining
            }
