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

@facial_analysis_bp.route('/eligible-sessions')
@login_required
@admin_required
@api_response
def get_eligible_sessions():
    """
    Get all sessions eligible for facial analysis processing

    Eligibility: Session completed with both PHQ and LLM assessments
    """
    with get_session() as db:
        from ...model.assessment.sessions import PHQResponse, LLMConversation

        # Get all sessions that are completed with both PHQ and LLM
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

        eligible_sessions = []
        stats = {'total': 0, 'pending': 0, 'processing': 0, 'completed': 0}

        for session, username, email in sessions:
            # Get PHQ and LLM assessment IDs
            phq_response = db.query(PHQResponse).filter_by(session_id=session.id).first()
            llm_conversation = db.query(LLMConversation).filter_by(session_id=session.id).first()

            if not phq_response or not llm_conversation:
                continue  # Skip sessions without both assessments

            # Get facial analysis status
            phq_analysis = db.query(SessionFacialAnalysis).filter_by(
                session_id=session.id,
                assessment_type='PHQ'
            ).first()

            llm_analysis = db.query(SessionFacialAnalysis).filter_by(
                session_id=session.id,
                assessment_type='LLM'
            ).first()

            phq_status = phq_analysis.status if phq_analysis else 'not_started'
            llm_status = llm_analysis.status if llm_analysis else 'not_started'

            # Count images for each assessment
            phq_images = db.query(func.count(CameraCapture.id)).filter_by(
                session_id=session.id,
                assessment_id=phq_response.id
            ).scalar() or 0

            llm_images = db.query(func.count(CameraCapture.id)).filter_by(
                session_id=session.id,
                assessment_id=llm_conversation.id
            ).scalar() or 0

            session_data = {
                'id': session.id,
                'username': username,
                'email': email,
                'session_number': session.session_number,
                'session_end': session.end_time.isoformat() if session.end_time else None,
                'phq_status': phq_status,
                'llm_status': llm_status,
                'phq_images_count': phq_images,
                'llm_images_count': llm_images,
                'total_images': phq_images + llm_images
            }

            eligible_sessions.append(session_data)

            # Update stats
            stats['total'] += 1
            if phq_status == 'completed' and llm_status == 'completed':
                stats['completed'] += 1
            elif phq_status == 'processing' or llm_status == 'processing':
                stats['processing'] += 1
            elif phq_status == 'not_started' and llm_status == 'not_started':
                stats['pending'] += 1

        return {
            'success': True,
            'sessions': eligible_sessions,
            'stats': stats
        }, 200


@facial_analysis_bp.route('/process/<session_id>', methods=['POST'])
@login_required
@admin_required
@api_response
def process_session(session_id):
    """
    Start facial analysis processing for BOTH PHQ and LLM assessments in a session

    Args:
        session_id: Session UUID

    Returns:
        {
            "success": bool,
            "message": str,
            "phq": {...},
            "llm": {...}
        }
    """
    # Check session exists
    with get_session() as db:
        session = db.query(AssessmentSession).filter_by(id=session_id).first()
        if not session:
            return {"success": False, "message": "Session not found"}, 404

    results = {
        "phq": None,
        "llm": None
    }

    errors = []

    # Process PHQ if it exists
    if session.phq_completed_at:
        try:
            phq_result = FacialAnalysisProcessingService.process_session_assessment(
                session_id=session_id,
                assessment_type='PHQ',
                media_save_path=current_app.media_save
            )
            # Convert Pydantic model to dict
            results['phq'] = phq_result.model_dump()

            # Check if processing itself failed
            if not phq_result.success:
                errors.append(f"PHQ: {phq_result.message}")
        except Exception as e:
            import traceback
            error_detail = f"PHQ exception: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_detail}")  # Log to console
            errors.append(f"PHQ processing exception: {str(e)}")
            results['phq'] = {"success": False, "message": str(e)}
    else:
        results['phq'] = {"success": False, "message": "PHQ assessment not completed"}

    # Process LLM if it exists
    if session.llm_completed_at:
        try:
            llm_result = FacialAnalysisProcessingService.process_session_assessment(
                session_id=session_id,
                assessment_type='LLM',
                media_save_path=current_app.media_save
            )
            # Convert Pydantic model to dict
            results['llm'] = llm_result.model_dump()

            # Check if processing itself failed
            if not llm_result.success:
                errors.append(f"LLM: {llm_result.message}")
        except Exception as e:
            import traceback
            error_detail = f"LLM exception: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_detail}")  # Log to console
            errors.append(f"LLM processing exception: {str(e)}")
            results['llm'] = {"success": False, "message": str(e)}
    else:
        results['llm'] = {"success": False, "message": "LLM assessment not completed"}

    # Determine overall success
    phq_success = results['phq'] and results['phq'].get('success', False)
    llm_success = results['llm'] and results['llm'].get('success', False)

    if phq_success and llm_success:
        return {
            "success": True,
            "message": "Both PHQ and LLM processed successfully",
            "phq": results['phq'],
            "llm": results['llm']
        }, 200
    elif phq_success or llm_success:
        return {
            "success": True,
            "message": "Partial success - check individual results",
            "phq": results['phq'],
            "llm": results['llm'],
            "errors": errors
        }, 200
    else:
        return {
            "success": False,
            "message": "Processing failed for both assessments",
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
    Batch process facial analysis for all eligible sessions.

    Returns aggregated results per session along with summary statistics.
    """
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

    results: List[Dict[str, Any]] = []
    summary = {
        "total_sessions": len(sessions),
        "completed": 0,
        "partial": 0,
        "failed": 0
    }

    for session, username, email in sessions:
        session_result: Dict[str, Any] = {
            "session_id": session.id,
            "username": username,
            "email": email,
            "phq": None,
            "llm": None,
            "errors": []
        }

        phq_success = False
        llm_success = False

        # Process PHQ
        if session.phq_completed_at:
            try:
                phq_result = FacialAnalysisProcessingService.process_session_assessment(
                    session_id=session.id,
                    assessment_type='PHQ',
                    media_save_path=current_app.media_save
                )
                phq_dict = phq_result.model_dump()
                session_result['phq'] = phq_dict
                if not phq_result.success:
                    session_result['errors'].append(f"PHQ: {phq_result.message}")
                else:
                    phq_success = True
            except Exception as e:
                session_result['phq'] = {"success": False, "message": str(e)}
                session_result['errors'].append(f"PHQ exception: {str(e)}")
        else:
            session_result['phq'] = {"success": False, "message": "PHQ assessment not completed"}
            session_result['errors'].append("PHQ assessment not completed")

        # Process LLM
        if session.llm_completed_at:
            try:
                llm_result = FacialAnalysisProcessingService.process_session_assessment(
                    session_id=session.id,
                    assessment_type='LLM',
                    media_save_path=current_app.media_save
                )
                llm_dict = llm_result.model_dump()
                session_result['llm'] = llm_dict
                if not llm_result.success:
                    session_result['errors'].append(f"LLM: {llm_result.message}")
                else:
                    llm_success = True
            except Exception as e:
                session_result['llm'] = {"success": False, "message": str(e)}
                session_result['errors'].append(f"LLM exception: {str(e)}")
        else:
            session_result['llm'] = {"success": False, "message": "LLM assessment not completed"}
            session_result['errors'].append("LLM assessment not completed")

        if phq_success and llm_success:
            summary['completed'] += 1
        elif phq_success or llm_success:
            summary['partial'] += 1
        else:
            summary['failed'] += 1

        results.append(session_result)

    overall_success = summary['completed'] > 0 and summary['failed'] == 0

    message = (
        f"Processed {summary['total_sessions']} sessions. "
        f"Completed: {summary['completed']}, "
        f"Partial: {summary['partial']}, "
        f"Failed: {summary['failed']}."
    )

    return {
        "success": overall_success,
        "message": message,
        "summary": summary,
        "results": results
    }, 200


@facial_analysis_bp.route('/status/<session_id>/<assessment_type>', methods=['GET'])
@login_required
@admin_required
@api_response
def get_processing_status(session_id, assessment_type):
    """
    Get processing status for a specific assessment

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
    Reuses dashboard query logic but for image viewing
    """
    with get_session() as db:
        # Get all completed sessions
        sessions = db.query(
            AssessmentSession,
            User.uname.label('username'),
            User.email.label('email')
        ).join(
            User, AssessmentSession.user_id == User.id
        ).filter(
            AssessmentSession.status == 'COMPLETED'
        ).all()

        sessions_data = []

        for session, username, email in sessions:
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
                sessions_data.append({
                    'session_id': session.id,
                    'user_id': session.user_id,
                    'username': username,
                    'email': email,
                    'session_number': session.session_number,
                    'end_time': session.end_time.isoformat() if session.end_time else None,
                    'phq_images': phq_images,
                    'llm_images': llm_images,
                    'total_images': total_images
                })

        return {
            'success': True,
            'sessions': sessions_data,
            'total': len(sessions_data)
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
