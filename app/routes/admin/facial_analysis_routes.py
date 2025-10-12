"""
Admin routes for facial analysis processing

Dedicated management page for processing facial expression analysis
"""

from flask import Blueprint, current_app, render_template
from flask_login import login_required, current_user
from ...decorators import admin_required, api_response
from ...services.facial_analysis.processingService import FacialAnalysisProcessingService
from ...db import get_session
from ...model.assessment.sessions import AssessmentSession, CameraCapture
from ...model.assessment.facial_analysis import SessionFacialAnalysis
from ...model.shared.users import User
from sqlalchemy import and_, func

facial_analysis_bp = Blueprint('facial_analysis', __name__, url_prefix='/admin/facial-analysis')


@facial_analysis_bp.route('/')
@login_required
@admin_required
def index():
    """Main facial analysis management page"""
    return render_template('admin/facial_analysis/index.html', user=current_user)

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
            results['phq'] = phq_result
        except Exception as e:
            errors.append(f"PHQ processing failed: {str(e)}")
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
            results['llm'] = llm_result
        except Exception as e:
            errors.append(f"LLM processing failed: {str(e)}")
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
            return {
                "success": True,
                "status": status['status'],
                "details": status
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
            "phq": phq_status or {"status": "not_started"},
            "llm": llm_status or {"status": "not_started"}
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
