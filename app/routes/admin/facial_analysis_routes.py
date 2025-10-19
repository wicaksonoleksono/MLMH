"""
Admin routes for facial analysis processing

Dedicated management page for processing facial expression analysis
"""

from flask import Blueprint, current_app, render_template, send_file, abort
from flask_login import login_required, current_user
from ...decorators import admin_required, api_response, raw_response
from ...services.facial_analysis.processingService import FacialAnalysisProcessingService
from ...db import get_session
from ...model.assessment.sessions import AssessmentSession, CameraCapture, PHQResponse, LLMConversation
from ...model.assessment.facial_analysis import SessionFacialAnalysis
from ...model.shared.users import User
from sqlalchemy import and_, func
import os
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

facial_analysis_bp = Blueprint('facial_analysis', __name__, url_prefix='/admin/facial-analysis')


@facial_analysis_bp.route('/')
@login_required
@admin_required
@raw_response
def index():
    """Main facial analysis management page"""
    return render_template('admin/facial_analysis/index.html', user=current_user)


@facial_analysis_bp.route('/processing')
@login_required
@admin_required
@raw_response
def processing():
    """Facial analysis processing management page"""
    return render_template('admin/facial_analysis/processing.html', user=current_user)

# DEPRECATED: Use /admin/ajax-dashboard-data?tab=facial-analysis instead
# This endpoint is kept for backward compatibility but is no longer used


@facial_analysis_bp.route('/process/<session_id>', methods=['POST'])
@login_required
@admin_required
@api_response
def process_session(session_id):
    """
    Queue facial analysis processing for BOTH PHQ and LLM assessments (ASYNC)

    Processing now happens in background. Returns immediately with task IDs.
    Use /status endpoint to check progress.

    Args:
        session_id: Session UUID

    Returns:
        {
            "success": bool,
            "message": str,
            "phq_task_id": str,
            "llm_task_id": str,
            "phq": {...task status...},
            "llm": {...task status...}
        }
    """
    from ...services.facial_analysis.backgroundProcessingService import FacialAnalysisBackgroundService
    from ...services.schedulerService import scheduler_service

    # Check session exists
    with get_session() as db:
        session = db.query(AssessmentSession).filter_by(id=session_id).first()
        if not session:
            return {"success": False, "message": "Session not found"}, 404

    results = {
        "phq": None,
        "llm": None,
        "phq_task_id": None,
        "llm_task_id": None
    }

    errors = []

    # Queue PHQ processing if it exists
    if session.phq_completed_at:
        try:
            phq_queue_result = FacialAnalysisBackgroundService.queue_processing_task(
                session_id=session_id,
                assessment_type='PHQ',
                media_save_path=current_app.media_save,
                scheduler=scheduler_service.scheduler
            )
            results['phq'] = phq_queue_result
            results['phq_task_id'] = phq_queue_result.get('task_id')

            if not phq_queue_result.get('success'):
                errors.append(f"PHQ: {phq_queue_result.get('message')}")
        except Exception as e:
            import traceback
            error_detail = f"PHQ queuing exception: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_detail}")
            errors.append(f"PHQ queuing exception: {str(e)}")
            results['phq'] = {"success": False, "message": str(e)}
    else:
        results['phq'] = {"success": False, "message": "PHQ assessment not completed"}

    # Queue LLM processing if it exists
    if session.llm_completed_at:
        try:
            llm_queue_result = FacialAnalysisBackgroundService.queue_processing_task(
                session_id=session_id,
                assessment_type='LLM',
                media_save_path=current_app.media_save,
                scheduler=scheduler_service.scheduler
            )
            results['llm'] = llm_queue_result
            results['llm_task_id'] = llm_queue_result.get('task_id')

            if not llm_queue_result.get('success'):
                errors.append(f"LLM: {llm_queue_result.get('message')}")
        except Exception as e:
            import traceback
            error_detail = f"LLM queuing exception: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_detail}")
            errors.append(f"LLM queuing exception: {str(e)}")
            results['llm'] = {"success": False, "message": str(e)}
    else:
        results['llm'] = {"success": False, "message": "LLM assessment not completed"}

    # Determine overall success (based on queuing, not processing result)
    phq_queued = results['phq'] and results['phq'].get('success', False)
    llm_queued = results['llm'] and results['llm'].get('success', False)

    if phq_queued and llm_queued:
        return {
            "success": True,
            "message": "Both PHQ and LLM queued for processing",
            "phq_task_id": results['phq_task_id'],
            "llm_task_id": results['llm_task_id'],
            "phq": results['phq'],
            "llm": results['llm']
        }, 202  # 202 Accepted - request accepted for processing
    elif phq_queued or llm_queued:
        return {
            "success": True,
            "message": "Processing queued (check individual status)",
            "phq_task_id": results['phq_task_id'],
            "llm_task_id": results['llm_task_id'],
            "phq": results['phq'],
            "llm": results['llm'],
            "errors": errors
        }, 202
    else:
        return {
            "success": False,
            "message": "Failed to queue processing for both assessments",
            "phq": results['phq'],
            "llm": results['llm'],
            "errors": errors
        }, 400


@facial_analysis_bp.route('/process-all', methods=['POST'])
@login_required
@admin_required
@api_response
def process_all_sessions():
    """
    Batch queue all eligible sessions for facial analysis processing.

    Uses the existing queue system (scheduler) to process sessions sequentially.
    Max 1 worker processes sessions one at a time, keeping memory usage low.
    Each session internally uses 4 gRPC workers for image parallelization.

    Returns immediately with queuing summary (actual processing happens in background).
    """
    from ...services.facial_analysis.backgroundProcessingService import FacialAnalysisBackgroundService
    from ...services.schedulerService import scheduler_service

    with get_session() as db:
        sessions = db.query(
            AssessmentSession,
            User.uname.label('username'),
            User.email.label('email')
        ).join(
            User, AssessmentSession.user_id == User.id
        ).filter(
            and_(
                AssessmentSession.status == 'COMPLETED',
                AssessmentSession.phq_completed_at.isnot(None),
                AssessmentSession.llm_completed_at.isnot(None)
            )
        ).all()

    if not sessions:
        return {
            "success": False,
            "message": "No eligible sessions found to process."
        }, 200

    queued_count = 0
    already_processing = 0
    already_completed = 0
    errors = []

    print(f"[INFO] Queuing {len(sessions)} sessions for processing...")

    for session, username, email in sessions:
        session_id = session.id

        # Queue PHQ if exists
        if session.phq_completed_at:
            try:
                phq_result = FacialAnalysisBackgroundService.queue_processing_task(
                    session_id=session_id,
                    assessment_type='PHQ',
                    media_save_path=current_app.media_save,
                    scheduler=scheduler_service.scheduler
                )
                status = phq_result.get('status', 'unknown')
                if status == 'queued':
                    queued_count += 1
                    print(f"[QUEUED] PHQ for {username} ({session_id[:8]})")
                elif status == 'already_processing':
                    already_processing += 1
                    print(f"[SKIP] PHQ for {username} - already processing")
                elif status == 'already_completed':
                    already_completed += 1
                    print(f"[SKIP] PHQ for {username} - already completed")
            except Exception as e:
                error_msg = f"Failed to queue PHQ for {username}: {str(e)}"
                errors.append(error_msg)
                print(f"[ERROR] {error_msg}")

        # Queue LLM if exists
        if session.llm_completed_at:
            try:
                llm_result = FacialAnalysisBackgroundService.queue_processing_task(
                    session_id=session_id,
                    assessment_type='LLM',
                    media_save_path=current_app.media_save,
                    scheduler=scheduler_service.scheduler
                )
                status = llm_result.get('status', 'unknown')
                if status == 'queued':
                    queued_count += 1
                    print(f"[QUEUED] LLM for {username} ({session_id[:8]})")
                elif status == 'already_processing':
                    already_processing += 1
                    print(f"[SKIP] LLM for {username} - already processing")
                elif status == 'already_completed':
                    already_completed += 1
                    print(f"[SKIP] LLM for {username} - already completed")
            except Exception as e:
                error_msg = f"Failed to queue LLM for {username}: {str(e)}"
                errors.append(error_msg)
                print(f"[ERROR] {error_msg}")

    message = (
        f"Queued {queued_count} assessments for processing. "
        f"Already processing: {already_processing}, "
        f"Already completed: {already_completed}."
    )

    if errors:
        message += f" Errors: {len(errors)}"

    print(f"[COMPLETE] Batch queuing complete: {message}")

    return {
        "success": queued_count > 0,
        "message": message,
        "summary": {
            "total_sessions": len(sessions),
            "queued": queued_count,
            "already_processing": already_processing,
            "already_completed": already_completed,
            "errors": len(errors)
        },
        "error_details": errors if errors else None
    }, 200


@facial_analysis_bp.route('/process-all/cancel', methods=['POST'])
@login_required
@admin_required
@api_response
def cancel_process_all():
    """
    Cancel all queued facial analysis tasks.

    Changes all 'queued' tasks to 'failed' status with cancellation message.
    Tasks already 'processing' will continue (can't kill gRPC calls).
    """
    from ...model.assessment.facial_analysis import SessionFacialAnalysis

    with get_session() as db:
        # Count queued tasks
        queued_count = db.query(SessionFacialAnalysis).filter_by(status='queued').count()

        if queued_count == 0:
            return {
                "success": False,
                "message": "No queued tasks to cancel"
            }, 400

        # Cancel all queued tasks
        db.query(SessionFacialAnalysis).filter_by(status='queued').update({
            'status': 'failed',
            'error_message': f'Cancelled by admin ({current_user.email})',
            'completed_at': datetime.utcnow()
        })
        db.commit()

        print(f"[CANCEL] Cancelled {queued_count} queued tasks by {current_user.email}")

    return {
        "success": True,
        "message": f"Cancelled {queued_count} queued tasks. Currently processing tasks will complete."
    }, 200


@facial_analysis_bp.route('/process-all/status', methods=['GET'])
@login_required
@admin_required
@api_response
def get_process_all_status():
    """
    Get real-time progress stats for all queued facial analysis tasks

    Returns counts of sessions by status: queued, processing, completed, failed
    """
    from ...model.assessment.facial_analysis import SessionFacialAnalysis
    from sqlalchemy import func

    with get_session() as db:
        # Get counts grouped by status
        status_counts = db.query(
            SessionFacialAnalysis.status,
            func.count(SessionFacialAnalysis.id).label('count')
        ).group_by(SessionFacialAnalysis.status).all()

        # Build result dict
        stats = {
            'queued': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0,
            'not_started': 0
        }

        for status, count in status_counts:
            if status in stats:
                stats[status] = count

        # Calculate totals
        total = sum(stats.values())
        in_progress = stats['queued'] + stats['processing']
        is_running = in_progress > 0

        return {
            "success": True,
            "is_running": is_running,
            "stats": stats,
            "total": total,
            "in_progress": in_progress,
            "progress_percentage": int((stats['completed'] + stats['failed']) / total * 100) if total > 0 else 0
        }, 200


@facial_analysis_bp.route('/task-status/<session_id>/<assessment_type>', methods=['GET'])
@login_required
@admin_required
@api_response
def get_task_status(session_id, assessment_type):
    """
    Get background processing task status for a specific assessment

    Args:
        session_id: Session UUID
        assessment_type: 'PHQ' or 'LLM'

    Returns:
        {
            "success": bool,
            "task_id": str,
            "status": str,  # 'queued', 'processing', 'completed', 'failed', 'not_found'
            "progress": int (0-100),
            "started_at": str (ISO format),
            "completed_at": str (ISO format),
            "error": str or None,
            "result": {...} or None
        }
    """
    from ...services.facial_analysis.backgroundProcessingService import FacialAnalysisBackgroundService

    # Validate assessment_type
    if assessment_type not in ['PHQ', 'LLM']:
        return {
            "success": False,
            "message": "Invalid assessment_type. Must be 'PHQ' or 'LLM'"
        }, 400

    try:
        status = FacialAnalysisBackgroundService.get_task_status(
            session_id=session_id,
            assessment_type=assessment_type
        )

        return {
            "success": True,
            "status": status.get('status'),
            "details": status
        }, 200

    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to get task status: {str(e)}"
        }, 500


@facial_analysis_bp.route('/status/<session_id>/<assessment_type>', methods=['GET'])
@login_required
@admin_required
@api_response
def get_processing_status(session_id, assessment_type):
    """
    Get processing status for a specific assessment (DEPRECATED - use /task-status instead)

    Args:
        session_id: Session UUID
        assessment_type: 'PHQ' or 'LLM'

    Returns:
        {
            "success": bool,
            "status": str,  # 'pending', 'processing', 'completed', 'failed'
            "details": {...}
        }
    """
    # Validate assessment_type
    if assessment_type not in ['PHQ', 'LLM']:
        return {
            "success": False,
            "message": "Invalid assessment_type. Must be 'PHQ' or 'LLM'"
        }, 400

    try:
        status = FacialAnalysisProcessingService.get_processing_status(
            session_id=session_id,
            assessment_type=assessment_type
        )

        if status:
            status_dict = status.model_dump()
            return {
                "success": True,
                "status": status_dict['status'],
                "details": status_dict
            }, 200
        else:
            return {
                "success": True,
                "status": "not_started",
                "details": {
                    "message": "Facial analysis not yet started for this assessment"
                }
            }, 200

    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to get status: {str(e)}"
        }, 500


@facial_analysis_bp.route('/session-status/<session_id>', methods=['GET'])
@login_required
@admin_required
@api_response
def get_session_status(session_id):
    """
    Get processing status for all assessments in a session

    Returns both PHQ and LLM status
    """
    try:
        phq_status = FacialAnalysisProcessingService.get_processing_status(
            session_id=session_id,
            assessment_type='PHQ'
        )

        llm_status = FacialAnalysisProcessingService.get_processing_status(
            session_id=session_id,
            assessment_type='LLM'
        )

        return {
            "success": True,
            "phq": phq_status.model_dump() if phq_status else {"status": "not_started"},
            "llm": llm_status.model_dump() if llm_status else {"status": "not_started"}
        }, 200

    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to get session status: {str(e)}"
        }, 500

@facial_analysis_bp.route('/health', methods=['GET'])
@login_required
@admin_required
@api_response
def check_grpc_health():
    """
    Check if gRPC facial analysis service is running

    Returns:
        {
            "success": bool,
            "healthy": bool,
            "message": str
        }
    """
    try:
        from ...facial_analysis.client.inference_client import FacialInferenceClient
        # Get gRPC config from env - NO FALLBACKS
        import os
        grpc_host = os.getenv('GRPC_FACIAL_ANALYSIS_HOST')
        grpc_port = os.getenv('GRPC_FACIAL_ANALYSIS_PORT')

        if not grpc_host or not grpc_port:
            raise ValueError("gRPC configuration missing in .env: GRPC_FACIAL_ANALYSIS_HOST and GRPC_FACIAL_ANALYSIS_PORT required")

        grpc_port = int(grpc_port)

        # Try health check
        with FacialInferenceClient(host=grpc_host, port=grpc_port) as client:
            health = client.health_check()

            return {
                "success": True,
                "healthy": health['healthy'],
                "message": health['message'],
                "config": {
                    "host": grpc_host,
                    "port": grpc_port
                }
            }, 200

    except Exception as e:
        return {
            "success": False,
            "healthy": False,
            "message": f"Health check failed: {str(e)}"
        }, 500


# ============================================================================
# IMAGE VIEWING ROUTES
# ============================================================================

@facial_analysis_bp.route('/sessions')
@login_required
@admin_required
@raw_response
def sessions_list():
    """Page to list all sessions with view images action"""
    return render_template('admin/facial_analysis/sessions.html', user=current_user)


@facial_analysis_bp.route('/sessions-data')
@login_required
@admin_required
@api_response
def get_sessions_data():
    """
    Get all completed sessions with image counts
    Now with pagination and search support
    """
    from flask import request

    # Get pagination and search parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    search_query = request.args.get('q', '').strip()

    # Limit per_page options
    if per_page not in [10, 15, 20, 50]:
        per_page = 15

    with get_session() as db:
        # Base query for completed sessions with images
        base_query = db.query(
            AssessmentSession,
            User.uname.label('username'),
            User.email.label('email'),
            User.id.label('user_id')
        ).join(
            User, AssessmentSession.user_id == User.id
        ).filter(
            AssessmentSession.status == 'COMPLETED'
        )

        # Apply search filter
        if search_query:
            search_filter = f"%{search_query}%"
            base_query = base_query.filter(
                (User.uname.ilike(search_filter)) |
                (User.email.ilike(search_filter))
            )

        # Order by username first, then session_number (to group sessions by user)
        base_query = base_query.order_by(User.uname.asc(), AssessmentSession.session_number.asc())

        # Get all matching sessions (we need to filter by image count first)
        all_sessions = base_query.all()

        # Build sessions data with image counts
        sessions_with_images = []

        for session, username, email, user_id in all_sessions:
            # Get PHQ and LLM assessment IDs
            phq_response = db.query(PHQResponse).filter_by(session_id=session.id).first()
            llm_conversation = db.query(LLMConversation).filter_by(session_id=session.id).first()

            # Count images for each assessment
            phq_images = 0
            llm_images = 0

            if phq_response:
                phq_images = db.query(func.count(CameraCapture.id)).filter_by(
                    session_id=session.id,
                    assessment_id=phq_response.id
                ).scalar() or 0

            if llm_conversation:
                llm_images = db.query(func.count(CameraCapture.id)).filter_by(
                    session_id=session.id,
                    assessment_id=llm_conversation.id
                ).scalar() or 0

            total_images = phq_images + llm_images

            # Only include sessions with images
            if total_images > 0:
                sessions_with_images.append({
                    'session_id': session.id,
                    'user_id': user_id,
                    'username': username,
                    'email': email,
                    'session_number': session.session_number,
                    'end_time': session.end_time.isoformat() if session.end_time else None,
                    'phq_images': phq_images,
                    'llm_images': llm_images,
                    'total_images': total_images
                })

        # Manual pagination on the filtered list
        total_count = len(sessions_with_images)
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

        # Ensure page is valid
        if page < 1:
            page = 1
        if page > total_pages and total_pages > 0:
            page = total_pages

        # Calculate pagination slice
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_sessions = sessions_with_images[start_idx:end_idx]

        return {
            'success': True,
            'sessions': paginated_sessions,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages,
                'prev_num': page - 1 if page > 1 else None,
                'next_num': page + 1 if page < total_pages else None
            },
            'search_query': search_query
        }


@facial_analysis_bp.route('/session/<session_id>/images')
@login_required
@admin_required
@raw_response
def view_session_images(session_id):
    """View all images for a specific session"""
    with get_session() as db:
        # Get session info
        session = db.query(AssessmentSession).join(
            User, AssessmentSession.user_id == User.id
        ).filter(AssessmentSession.id == session_id).first()

        if not session:
            abort(404, "Session not found")

        # Get PHQ and LLM assessments
        phq_response = db.query(PHQResponse).filter_by(session_id=session_id).first()
        llm_conversation = db.query(LLMConversation).filter_by(session_id=session_id).first()

        # Get PHQ images
        phq_captures = []
        if phq_response:
            phq_captures = db.query(CameraCapture).filter_by(
                session_id=session_id,
                assessment_id=phq_response.id,
                capture_type='PHQ'
            ).all()

        # Get LLM images
        llm_captures = []
        if llm_conversation:
            llm_captures = db.query(CameraCapture).filter_by(
                session_id=session_id,
                assessment_id=llm_conversation.id,
                capture_type='LLM'
            ).all()

        return render_template(
            'admin/facial_analysis/session_images.html',
            user=current_user,
            session=session,
            phq_captures=phq_captures,
            llm_captures=llm_captures
        )


@facial_analysis_bp.route('/image/<path:filename>')
@login_required
@admin_required
@raw_response
def serve_image(filename):
    """
    Serve an image from the media_save path

    Args:
        filename: Image filename (e.g., 'image_123.jpg')

    Returns:
        Image file
    """
    try:
        media_save_path = current_app.media_save
        image_path = os.path.join(media_save_path, filename)

        # Security check: ensure the file is within media_save
        if not os.path.abspath(image_path).startswith(os.path.abspath(media_save_path)):
            abort(403, "Access denied")

        if not os.path.exists(image_path):
            abort(404, "Image not found")

        return send_file(image_path, mimetype='image/jpeg')

    except Exception as e:
        abort(500, f"Error serving image: {str(e)}")


# ============================================================================
# DELETE / RE-ANALYZE ROUTES
# ============================================================================

@facial_analysis_bp.route('/delete/<session_id>/<assessment_type>', methods=['DELETE'])
@login_required
@admin_required
@api_response
def delete_analysis(session_id, assessment_type):
    """
    Delete facial analysis for a specific assessment

    Deletes both the JSONL file and database record

    Args:
        session_id: Session UUID
        assessment_type: 'PHQ' or 'LLM'

    Returns:
        {"success": bool, "message": str}
    """
    # Validate assessment_type
    if assessment_type not in ['PHQ', 'LLM']:
        return {
            "success": False,
            "message": "Invalid assessment_type. Must be 'PHQ' or 'LLM'"
        }, 400

    try:
        with get_session() as db:
            # Get the analysis record
            analysis = db.query(SessionFacialAnalysis).filter_by(
                session_id=session_id,
                assessment_type=assessment_type
            ).first()

            if not analysis:
                return {
                    "success": False,
                    "message": f"No {assessment_type} analysis found for this session"
                }, 404

            # Delete JSONL file if it exists
            jsonl_path = os.path.join(current_app.media_save, analysis.jsonl_file_path)
            if os.path.exists(jsonl_path):
                try:
                    os.remove(jsonl_path)
                except Exception as e:
                    print(f"[WARNING] Failed to delete JSONL file {jsonl_path}: {str(e)}")

            # Delete database record
            db.delete(analysis)
            db.commit()

        return {
            "success": True,
            "message": f"{assessment_type} analysis deleted successfully"
        }, 200

    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to delete analysis: {str(e)}"
        }, 500


@facial_analysis_bp.route('/cancel/<session_id>/<assessment_type>', methods=['POST'])
@login_required
@admin_required
@api_response
def cancel_processing(session_id, assessment_type):
    """
    Cancel ongoing facial analysis processing

    This endpoint is used to stop stuck or long-running processing.
    It marks the analysis as failed and deletes any partial results.

    Args:
        session_id: Session UUID
        assessment_type: 'PHQ' or 'LLM'

    Returns:
        {"success": bool, "message": str}
    """
    # Validate assessment_type
    if assessment_type not in ['PHQ', 'LLM']:
        return {
            "success": False,
            "message": "Invalid assessment_type. Must be 'PHQ' or 'LLM'"
        }, 400

    try:
        with get_session() as db:
            # Get the analysis record
            analysis = db.query(SessionFacialAnalysis).filter_by(
                session_id=session_id,
                assessment_type=assessment_type
            ).first()

            if not analysis:
                return {
                    "success": False,
                    "message": f"No {assessment_type} analysis found for this session"
                }, 404

            # Check if it's actually processing
            if analysis.status != 'processing':
                return {
                    "success": False,
                    "message": f"Cannot cancel - status is '{analysis.status}', not 'processing'"
                }, 400

            # Delete partial JSONL file if it exists
            jsonl_path = os.path.join(current_app.media_save, analysis.jsonl_file_path)
            if os.path.exists(jsonl_path):
                try:
                    os.remove(jsonl_path)
                    print(f"[INFO] Deleted partial JSONL file: {jsonl_path}")
                except Exception as e:
                    print(f"[WARNING] Failed to delete JSONL file {jsonl_path}: {str(e)}")

            # Mark as cancelled (using failed status with specific message)
            from datetime import datetime
            analysis.status = 'failed'
            analysis.error_message = 'Processing cancelled by admin'
            analysis.completed_at = datetime.utcnow()
            db.commit()

            print(f"[INFO] Cancelled {assessment_type} processing for session {session_id}")

        return {
            "success": True,
            "message": f"{assessment_type} processing cancelled successfully"
        }, 200

    except Exception as e:
        import traceback
        print(f"[ERROR] Cancel processing failed: {str(e)}\n{traceback.format_exc()}")
        return {
            "success": False,
            "message": f"Failed to cancel processing: {str(e)}"
        }, 500


@facial_analysis_bp.route('/reanalyze/<session_id>/<assessment_type>', methods=['POST'])
@login_required
@admin_required
@api_response
def reanalyze_assessment(session_id, assessment_type):
    """
    Re-analyze a specific assessment

    Deletes existing analysis and triggers processing again

    Args:
        session_id: Session UUID
        assessment_type: 'PHQ' or 'LLM'

    Returns:
        {"success": bool, "message": str, "result": {...}}
    """
    # Validate assessment_type
    if assessment_type not in ['PHQ', 'LLM']:
        return {
            "success": False,
            "message": "Invalid assessment_type. Must be 'PHQ' or 'LLM'"
        }, 400

    try:
        # Step 1: Delete existing analysis if it exists
        with get_session() as db:
            analysis = db.query(SessionFacialAnalysis).filter_by(
                session_id=session_id,
                assessment_type=assessment_type
            ).first()

            if analysis:
                # Delete JSONL file
                jsonl_path = os.path.join(current_app.media_save, analysis.jsonl_file_path)
                if os.path.exists(jsonl_path):
                    try:
                        os.remove(jsonl_path)
                    except Exception as e:
                        print(f"[WARNING] Failed to delete JSONL file: {str(e)}")

                # Delete database record
                db.delete(analysis)
                db.commit()

        # Step 2: Trigger processing again
        result = FacialAnalysisProcessingService.process_session_assessment(
            session_id=session_id,
            assessment_type=assessment_type,
            media_save_path=current_app.media_save
        )

        result_dict = result.model_dump()

        if result.success:
            return {
                "success": True,
                "message": f"{assessment_type} re-analysis completed successfully",
                "result": result_dict
            }, 200
        else:
            return {
                "success": False,
                "message": f"{assessment_type} re-analysis failed: {result.message}",
                "result": result_dict
            }, 400

    except Exception as e:
        import traceback
        error_detail = f"{assessment_type} re-analysis exception: {str(e)}\n{traceback.format_exc()}"
        print(f"[ERROR] {error_detail}")
        return {
            "success": False,
            "message": f"Re-analysis failed: {str(e)}"
        }, 500
