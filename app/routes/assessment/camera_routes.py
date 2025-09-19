# app/routes/assessment/camera_routes.py
from flask import Blueprint, request
from flask_login import current_user
from ...decorators import api_response, user_required
from ...services.session.sessionManager import SessionManager
from ...services.assessment.cameraAssessmentService import CameraAssessmentService
from ...db import get_session
from ...model.assessment.sessions import CameraCapture

camera_assessment_bp = Blueprint('camera_assessment', __name__, url_prefix='/assessment/camera')


@camera_assessment_bp.route('/settings/<session_id>', methods=['GET'])
@user_required
@api_response
def get_camera_settings(session_id):
    """Get camera settings for assessment session - clean SOC"""
    if not SessionManager.validate_user_session(session_id, current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    return CameraAssessmentService.get_session_settings(session_id)


@camera_assessment_bp.route('/upload-single/<session_id>', methods=['POST'])
@user_required
@api_response
def upload_single_image(session_id):
    """Upload single image immediately - CLEAN BATCH APPROACH"""
    if not SessionManager.validate_user_session(session_id, current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    return CameraAssessmentService.process_single_upload(session_id, request)


@camera_assessment_bp.route('/create-batch/<assessment_id>', methods=['POST'])
@user_required
@api_response
def create_batch_capture(assessment_id):
    """Create batch capture with assessment_id directly - ASSESSMENT-FIRST APPROACH"""
    # Validate assessment belongs to current user (via session)
    if not CameraAssessmentService.validate_assessment_access(assessment_id, current_user.id):
        return {"message": "Assessment not found or access denied"}, 403
    
    data = request.get_json()
    filenames = data.get('filenames', [])
    capture_type = data.get('capture_type', 'PHQ')
    capture_metadata = data.get('capture_metadata', {})
    
    # DEBUG: Log what we're receiving from frontend
  
    if not filenames:
        return {"status": "SNAFU", "error": "No filenames provided"}, 400
    
    return CameraAssessmentService.create_batch_capture_with_assessment_id(
        assessment_id=assessment_id,
        filenames=filenames,
        capture_type=capture_type,
        capture_metadata=capture_metadata
    )


@camera_assessment_bp.route('/link-to-assessment/<session_id>', methods=['POST'])
@user_required
@api_response
def link_captures_to_assessment(session_id):
    """Link existing camera captures to assessment - INCREMENTAL APPROACH"""
    if not SessionManager.validate_user_session(session_id, current_user.id):
        return {"message": "Session not found or access denied"}, 403
    data = request.get_json()
    assessment_id = data.get('assessment_id')
    assessment_type = data.get('assessment_type')
    if not assessment_id or not assessment_type:
        return {"status": "SNAFU", "error": "assessment_id and assessment_type required"}, 400
    if assessment_type not in ['PHQ', 'LLM']:
        return {"status": "SNAFU", "error": "Invalid assessment type"}, 400
    return CameraAssessmentService.link_incremental_captures_to_assessment(
        session_id=session_id,
        assessment_id=assessment_id,
        assessment_type=assessment_type
    )



@camera_assessment_bp.route('/captures/<session_id>', methods=['GET'])
@user_required
@api_response
def get_session_captures(session_id):
    """Get all camera captures for a session - clean SOC"""
    if not SessionManager.validate_user_session(session_id, current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    return CameraAssessmentService.get_session_captures(session_id)