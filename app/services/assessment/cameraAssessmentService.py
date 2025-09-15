# app/services/assessment/cameraAssessmentService.py
from typing import Dict, Any, List
from datetime import datetime
from flask import request
from ..camera.cameraCaptureService import CameraCaptureService
from ..camera.cameraStorageService import CameraStorageService
from ...db import get_session
from ...model.assessment.sessions import CameraCapture, PHQResponse, LLMConversation


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
                "capture_metadata": capture.capture_metadata,
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
        """Process single image upload - STORE FILE ONLY, NO DB RECORD"""
        camera_settings = CameraCaptureService.get_camera_settings_for_session(session_id)
        if not camera_settings:
            return {"status": "SNAFU", "error": "No camera settings configured"}
        file = request.files.get('image')
        if not file or not file.filename:
            return {"status": "SNAFU", "error": "No image file provided"}
        trigger = request.form.get('trigger', 'unknown')
        timing_str = request.form.get('timing')
        timing_data = None
        if timing_str:
            try:
                import json
                timing_data = json.loads(timing_str)
            except:
                pass
        
        try:
            # Save file to disk AND incrementally add to database JSON array
            file_data = file.read()
            filename = CameraStorageService.save_image_locally(
                session_id=session_id,
                file_data=file_data
            )
            
            # INCREMENTAL: Add filename to database JSON array immediately with timing data
            CameraStorageService.add_filename_to_session_incrementally(
                session_id=session_id,
                filename=filename,
                trigger=trigger,
                assessment_timing=timing_data
            )
            
            # Return filename for frontend to track locally
            upload_response = {
                "status": "OLKORECT",
                "data": {
                    "filename": filename,
                    "trigger": trigger,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            
            return upload_response
            
        except Exception as e:
            return {"status": "SNAFU", "error": f"Failed to save image: {str(e)}"}

    @staticmethod
    def validate_assessment_access(assessment_id: str, user_id: str) -> bool:
        """Validate that assessment belongs to current user via session"""
        with get_session() as db:
            # Check PHQ assessment
            phq_record = db.query(PHQResponse).filter_by(id=assessment_id).first()
            if phq_record:
                from ..sessionService import SessionService
                session = SessionService.get_session(phq_record.session_id)
                return session and str(session.user_id) == str(user_id)
            
            # Check LLM assessment
            llm_record = db.query(LLMConversation).filter_by(id=assessment_id).first()
            if llm_record:
                from ..sessionService import SessionService
                session = SessionService.get_session(llm_record.session_id)
                return session and str(session.user_id) == str(user_id)
                
            return False

    @staticmethod
    def create_batch_capture_with_assessment_id(
        assessment_id: str,
        filenames: List[str],
        capture_type: str,  # 'PHQ' or 'LLM'
        capture_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create batch capture record with assessment_id directly - ASSESSMENT-FIRST APPROACH"""
        try:
            # Get session_id from assessment record
            session_id = None
            with get_session() as db:
                if capture_type.upper() == 'PHQ':
                    phq_record = db.query(PHQResponse).filter_by(id=assessment_id).first()
                    if phq_record:
                        session_id = phq_record.session_id
                elif capture_type.upper() == 'LLM':
                    llm_record = db.query(LLMConversation).filter_by(id=assessment_id).first()
                    if llm_record:
                        session_id = llm_record.session_id
                        
            if not session_id:
                raise ValueError(f"Assessment {assessment_id} not found or invalid type {capture_type}")

            # DEBUG: Log what we're passing to storage service
            print(f" CAMERA SERVICE DEBUG:")
            print(f"   session_id: {session_id}")
            print(f"   assessment_id: {assessment_id}")  
            print(f"   filenames: {filenames} (type: {type(filenames)}, length: {len(filenames)})")
            print(f"   capture_type: {capture_type}")
            
            capture_record = CameraStorageService.create_batch_capture_with_assessment_id(
                session_id=session_id,
                assessment_id=assessment_id,
                filenames=filenames,
                capture_type=capture_type,
                capture_metadata=capture_metadata
            )
            
            # DEBUG: Log what we got back from database
            print(f" AFTER DB SAVE:")
            print(f"   capture_record.id: {capture_record.id}")
            print(f"   capture_record.filenames: {capture_record.filenames} (type: {type(capture_record.filenames)})")
            print(f"   capture_record.assessment_id: {capture_record.assessment_id}")
            
            return {
                "status": "OLKORECT",
                "data": {
                    "capture_id": capture_record.id,
                    "assessment_id": capture_record.assessment_id,
                    "filenames": capture_record.filenames,
                    "capture_type": capture_record.capture_type,
                    "created_at": capture_record.created_at.isoformat()
                }
            }
            
        except Exception as e:
            print(f"Error creating batch capture with assessment_id: {e}")
            return {"status": "SNAFU", "error": str(e)}

    @staticmethod
    def link_incremental_captures_to_assessment(
        session_id: str,
        assessment_id: str, 
        assessment_type: str
    ) -> Dict[str, Any]:
        """Link existing unlinked captures to assessment - INCREMENTAL APPROACH"""
        try:
            capture_record = CameraStorageService.link_session_captures_to_assessment(
                session_id=session_id,
                assessment_id=assessment_id,
                assessment_type=assessment_type
            )
            
            if capture_record:
                return {
                    "status": "OLKORECT",
                    "data": {
                        "capture_id": capture_record.id,
                        "assessment_id": capture_record.assessment_id,
                        "filenames_count": len(capture_record.filenames),
                        "capture_type": capture_record.capture_type
                    }
                }
            else:
                return {
                    "status": "SNAFU",
                    "error": "No unlinked captures found for session"
                }
        except Exception as e:
            print(f"Error linking captures: {e}")
            return {"status": "SNAFU", "error": str(e)}

    @staticmethod
    def create_batch_capture(
        session_id: str,
        filenames: List[str],
        capture_type: str,  # 'PHQ' or 'LLM'
        capture_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create single batch capture record with all filenames and metadata"""
        try:
            capture_record = CameraStorageService.create_batch_capture(
                session_id=session_id,
                filenames=filenames,
                capture_type=capture_type,
                capture_metadata=capture_metadata
            )
            
            response_data = {
                "status": "OLKORECT",
                "data": {
                    "capture_id": capture_record.id,
                    "filenames": capture_record.filenames,
                    "capture_type": capture_record.capture_type,
                    "created_at": capture_record.created_at.isoformat()
                }
            }
            
            print(f" BACKEND RESPONSE: {response_data}")
            return response_data
            
        except Exception as e:
            return {"status": "SNAFU", "error": f"Failed to create batch capture: {str(e)}"}

    @staticmethod
    def auto_link_captures_to_assessment(
        session_id: str,
        assessment_type: str  # 'PHQ' or 'LLM'
    ) -> Dict[str, Any]:
        """Automatically link unlinked camera captures to newly created assessment records"""
        try:
            with get_session() as db:
                # Get the latest assessment record for this session and type
                if assessment_type == 'PHQ':
                    assessment_record = db.query(PHQResponse).filter_by(session_id=session_id).first()
                elif assessment_type == 'LLM':
                    assessment_record = db.query(LLMConversation).filter_by(session_id=session_id).first()
                else:
                    return {"status": "SNAFU", "error": f"Invalid assessment type: {assessment_type}"}
                
                if not assessment_record:
                    return {"status": "SNAFU", "error": f"No {assessment_type} record found for session {session_id}"}
                
                # Debug: Log what we're looking for
                print(f" Auto-link debug - session_id: {session_id}, assessment_type: {assessment_type}")
                print(f" Auto-link debug - assessment record ID: {assessment_record.id}")
                
                # Find ALL captures for this session first (for debugging)
                all_session_captures = db.query(CameraCapture).filter(
                    CameraCapture.session_id == session_id
                ).all()
                print(f" Auto-link debug - Total captures for session: {len(all_session_captures)}")
                for capture in all_session_captures:
                    print(f"  - Capture {capture.id}: type={capture.capture_type}, assessment_id={capture.assessment_id}")
                
                # Find unlinked captures for this session and assessment type
                unlinked_captures = db.query(CameraCapture).filter(
                    CameraCapture.session_id == session_id,
                    CameraCapture.capture_type == assessment_type,
                    CameraCapture.assessment_id.is_(None)
                ).all()
                
                print(f" Auto-link debug - Unlinked {assessment_type} captures found: {len(unlinked_captures)}")
                
                linked_count = 0
                for capture in unlinked_captures:
                    print(f"   Linking capture {capture.id} to assessment {assessment_record.id}")
                    capture.assessment_id = assessment_record.id
                    linked_count += 1
                
                db.commit()
                
                print(f" Auto-linking completed - linked {linked_count} captures")
                
                return {
                    "status": "OLKORECT",
                    "data": {
                        "session_id": session_id,
                        "assessment_type": assessment_type,
                        "assessment_id": assessment_record.id,
                        "captures_linked": linked_count
                    }
                }
                
        except Exception as e:
            print(f" Auto-linking failed: {str(e)}")
            return {"status": "SNAFU", "error": f"Failed to auto-link captures: {str(e)}"}

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
                    print(f" Cleaned up {cleaned_count} unlinked camera captures from session {session_id}")
                
                return {
                    "status": "OLKORECT",
                    "data": {
                        "session_id": session_id,
                        "captures_cleaned": cleaned_count
                    }
                }
                
        except Exception as e:
            return {"status": "SNAFU", "error": f"Failed to cleanup captures: {str(e)}"}