# app/services/assessment/cameraAssessmentService.py
from typing import Dict, Any
from flask import request
from ..camera.cameraCaptureService import CameraCaptureService
from ..camera.cameraStorageService import CameraStorageService
from ...db import get_session
from ...model.assessment.sessions import CameraCapture


class CameraAssessmentService:

    @staticmethod
    def get_session_settings(session_id: str) -> Dict[str, Any]:
        """Get camera settings for assessment session"""
        camera_settings = CameraCaptureService.get_camera_settings_for_session(session_id)
        
        if not camera_settings:
            return {"status": "SNAFU", "error": "No camera settings configured"}
        
        settings_dict = CameraCaptureService.create_settings_snapshot(camera_settings)
        
        return {
            "status": "OLKORECT",
            "data": {
                "settings": settings_dict,
                "session_id": session_id
            }
        }


    @staticmethod
    def get_session_captures(session_id: str) -> Dict[str, Any]:
        """Get all captures for session using unified storage service"""
        captures = CameraStorageService.get_session_captures(session_id)
        
        captures_data = []
        for capture in captures:
            captures_data.append({
                "id": capture.id,
                "filename": capture.filename,
                "file_size_bytes": capture.file_size_bytes,
                "capture_trigger": capture.capture_trigger,
                "timestamp": capture.timestamp.isoformat(),
                "phq_response_id": capture.phq_response_id,
                "llm_conversation_id": capture.llm_conversation_id
            })
        
        return {
            "status": "OLKORECT",
            "data": {
                "session_id": session_id,
                "captures": captures_data,
                "total_captures": len(captures_data)
            }
        }

    @staticmethod
    def process_single_upload(session_id: str, request) -> Dict[str, Any]:
        """Process single image upload immediately - hybrid approach"""
        camera_settings = CameraCaptureService.get_camera_settings_for_session(session_id)
        if not camera_settings:
            return {"status": "SNAFU", "error": "No camera settings configured"}
        
        # Get single file and metadata
        file = request.files.get('image')
        if not file or not file.filename:
            return {"status": "SNAFU", "error": "No image file provided"}
        
        # Get metadata
        trigger = request.form.get('trigger', 'unknown')
        
        # Validate trigger
        if not CameraCaptureService.should_capture_on_trigger(camera_settings, trigger):
            return {"status": "SNAFU", "error": f"Trigger '{trigger}' not allowed for current settings"}
        
        try:
            # Use unified storage service - save immediately with NULL response IDs
            file_data = file.read()
            capture_record = CameraStorageService.save_image(
                session_id=session_id,
                file_data=file_data,
                trigger=trigger,
                phq_response_id=None,  # Will be linked later
                llm_conversation_id=None  # Will be linked later
            )
            
            return {
                "status": "OLKORECT",
                "data": {
                    "capture_id": capture_record.id,
                    "filename": capture_record.filename,
                    "trigger": capture_record.capture_trigger,
                    "timestamp": capture_record.timestamp.isoformat()
                }
            }
            
        except Exception as e:
            return {"status": "SNAFU", "error": f"Failed to save image: {str(e)}"}

    @staticmethod
    def link_captures_to_responses(session_id: str, request) -> Dict[str, Any]:
        """Link capture IDs to PHQ/LLM response IDs - hybrid approach"""
        data = request.get_json()
        if not data:
            return {"status": "SNAFU", "error": "No JSON data provided"}
        
        capture_ids = data.get('capture_ids', [])
        phq_response_ids = data.get('phq_response_ids', [])
        llm_conversation_ids = data.get('llm_conversation_ids', [])
        
        if not capture_ids:
            return {"status": "SNAFU", "error": "No capture_ids provided"}
        
        try:
            with get_session() as db:
                updated_count = 0
                
                for capture_id in capture_ids:
                    capture = db.query(CameraCapture).filter_by(
                        id=capture_id,
                        assessment_session_id=session_id
                    ).first()
                    
                    if capture:
                        # Link to PHQ responses if provided
                        if phq_response_ids:
                            # Link to first available PHQ response
                            if len(phq_response_ids) > 0:
                                capture.phq_response_id = phq_response_ids[0]
                        
                        # Link to LLM conversations if provided
                        if llm_conversation_ids:
                            # Link to first available LLM conversation
                            if len(llm_conversation_ids) > 0:
                                capture.llm_conversation_id = llm_conversation_ids[0]
                        
                        updated_count += 1
                
                db.commit()
                
                return {
                    "status": "OLKORECT",
                    "data": {
                        "session_id": session_id,
                        "captures_updated": updated_count,
                        "capture_ids_processed": capture_ids
                    }
                }
                
        except Exception as e:
            return {"status": "SNAFU", "error": f"Failed to link captures: {str(e)}"}