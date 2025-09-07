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
                "session_id": capture.session_id,
                "assessment_id": capture.assessment_id,
                "filenames": capture.filenames,
                "capture_type": capture.capture_type,
                "created_at": capture.created_at.isoformat() if capture.created_at else None
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
        """Link all session captures to single assessment record ID - JSON structure approach"""
        data = request.get_json()
        if not data:
            return {"status": "SNAFU", "error": "No JSON data provided"}
        
        # Get the new linking data
        capture_ids = data.get('capture_ids', [])
        assessment_record_id = data.get('assessment_record_id')
        assessment_type = data.get('assessment_type', 'phq')
        
        if not capture_ids or not assessment_record_id:
            return {"status": "SNAFU", "error": "capture_ids and assessment_record_id are required"}
        
        try:
            with get_session() as db:
                updated_count = 0
                already_linked_count = 0
                
                # Process each capture and link to assessment record
                for capture_id in capture_ids:
                    capture = db.query(CameraCapture).filter_by(
                        id=capture_id,
                        session_id=session_id
                    ).first()
                    
                    if capture:
                        if capture.assessment_id:
                            already_linked_count += 1
                            print(f" Capture {capture_id} already linked to assessment {capture.assessment_id}")
                            continue
                        
                        # Link to assessment record using new model structure
                        capture.assessment_id = assessment_record_id
                        capture.capture_type = assessment_type.upper()
                        print(f"! Linked capture {capture_id} to {assessment_type.upper()} record {assessment_record_id}")
                        
                        updated_count += 1
                
                db.commit()
                
                return {
                    "status": "OLKORECT",
                    "data": {
                        "session_id": session_id,
                        "captures_updated": updated_count,
                        "captures_already_linked": already_linked_count,
                        "assessment_record_id": assessment_record_id,
                        "assessment_type": assessment_type,
                        "contamination_prevented": already_linked_count > 0
                    }
                }
                
        except Exception as e:
            return {"status": "SNAFU", "error": f"Failed to link captures: {str(e)}"}

    @staticmethod
    def cleanup_unlinked_captures(session_id: str) -> Dict[str, Any]:
        """Clean up unlinked captures from session to prevent cross-assessment contamination"""
        try:
            with get_session() as db:
                # Find captures that are unlinked (no assessment association)
                unlinked_captures = db.query(CameraCapture).filter(
                    CameraCapture.session_id == session_id,
                    CameraCapture.assessment_id.is_(None)
                ).all()
                
                cleaned_count = len(unlinked_captures)
                
                if cleaned_count > 0:
                    # Delete the capture records (files remain on disk for debugging)
                    for capture in unlinked_captures:
                        db.delete(capture)
                    
                    db.commit()
                    print(f"🧹 Cleaned up {cleaned_count} unlinked camera captures from session {session_id}")
                
                return {
                    "status": "OLKORECT",
                    "data": {
                        "session_id": session_id,
                        "captures_cleaned": cleaned_count
                    }
                }
                
        except Exception as e:
            return {"status": "SNAFU", "error": f"Failed to cleanup captures: {str(e)}"}