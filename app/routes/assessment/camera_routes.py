# app/routes/assessment/camera_routes.py
from flask import Blueprint, request
from flask_login import current_user
from ...decorators import api_response, user_required
from ...services.sessionService import SessionService
from ...services.assessment.cameraAssessmentService import CameraAssessmentService

camera_assessment_bp = Blueprint('camera_assessment', __name__, url_prefix='/assessment/camera')


@camera_assessment_bp.route('/settings/<session_id>', methods=['GET'])
@user_required
@api_response
def get_camera_settings(session_id):
    """Get camera settings for assessment session - clean SOC"""
    if not SessionService.validate_user_session(session_id, current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    return CameraAssessmentService.get_session_settings(session_id)




@camera_assessment_bp.route('/upload-single/<session_id>', methods=['POST'])
@user_required
@api_response
def upload_single_image(session_id):
    """Upload single image immediately - hybrid approach"""
    if not SessionService.validate_user_session(session_id, current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    return CameraAssessmentService.process_single_upload(session_id, request)


@camera_assessment_bp.route('/link-responses/<session_id>', methods=['POST'])
@user_required
@api_response
def link_capture_responses(session_id):
    """Link capture IDs to PHQ/LLM response IDs - hybrid approach"""
    if not SessionService.validate_user_session(session_id, current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    return CameraAssessmentService.link_captures_to_responses(session_id, request)


@camera_assessment_bp.route('/captures/<session_id>', methods=['GET'])
@user_required
@api_response
def get_session_captures(session_id):
    """Get all camera captures for a session - clean SOC"""
    if not SessionService.validate_user_session(session_id, current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    return CameraAssessmentService.get_session_captures(session_id)