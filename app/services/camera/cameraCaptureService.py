# app/services/camera/cameraCaptureService.py
import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from flask import current_app
from ...db import get_session
from ...model.assessment.sessions import CameraCapture, AssessmentSession
from ...model.admin.camera import CameraSettings
from ..session.sessionTimingService import SessionTimingService


class CameraCaptureService:
    """Service for handling camera capture operations with settings integration"""

    @staticmethod
    def get_upload_path() -> str:
        """Get the static directory path dynamically"""
        return current_app.media_save

    @staticmethod
    def ensure_upload_directory():
        """Ensure the upload directory exists"""
        upload_path = CameraCaptureService.get_upload_path()
        os.makedirs(upload_path, exist_ok=True)
        return upload_path

    @staticmethod
    def delete_capture_file(filename: str) -> bool:
        """Delete camera capture file from disk"""
        try:
            upload_path = CameraCaptureService.get_upload_path()
            file_path = os.path.join(upload_path, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            return False

    @staticmethod
    def generate_filename(timestamp: datetime, assessment_type: str, target_id: str, username: str = None, session_number: int = None) -> str:
        """Generate filename: {username}_s{session_number}_{timestamp}_{type}_{target_id_short}.jpg"""
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
        short_id = target_id[:8]
        
        if username and session_number:
            # Clean username (remove spaces, special chars)
            clean_username = "".join(c for c in username if c.isalnum() or c in ('_', '-')).lower()
            return f"{clean_username}_s{session_number}_{timestamp_str}_{assessment_type}_{short_id}.jpg"
        else:
            # Fallback to old format
            return f"{timestamp_str}_{assessment_type}_{short_id}.jpg"

    @staticmethod
    def save_capture(
        session_id: str,
        file_data: bytes,
        capture_trigger: str,
        assessment_id: Optional[str] = None,
        capture_type: str = 'GENERAL',
        camera_settings_snapshot: Optional[Dict[str, Any]] = None
    ) -> CameraCapture:
        """Save camera capture file and database record"""
        
        # Ensure upload directory exists
        upload_path = CameraCaptureService.ensure_upload_directory()
        
        # Get session info for filename
        username = None
        session_number = None
        with get_session() as db:
            from ...model.assessment.sessions import AssessmentSession
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if session and session.user:
                username = session.user.uname
                session_number = session.session_number
        
        # Generate filename based on context
        timestamp = datetime.utcnow()
        assessment_type = capture_type.lower()
        target_id = assessment_id or session_id
        
        filename = CameraCaptureService.generate_filename(timestamp, assessment_type, target_id, username, session_number)
        full_path = os.path.join(upload_path, filename)
        
        # Save file to disk
        with open(full_path, 'wb') as f:
            f.write(file_data)
        
        file_size = len(file_data)
        
        # Calculate session time for this capture
        session_time = SessionTimingService.get_session_time(session_id, timestamp)
        
        # Prepare capture metadata with session timing
        capture_metadata = {
            "session_time": session_time,  # Unified session timing starting from 0
            "capture_trigger": capture_trigger,
            "file_size": file_size,
            "timestamp_iso": timestamp.isoformat()
        }
        
        # Merge with any additional camera settings snapshot
        if camera_settings_snapshot:
            capture_metadata.update(camera_settings_snapshot)
        
        # Save database record using new model structure
        with get_session() as db:
            capture = CameraCapture(
                session_id=session_id,
                assessment_id=assessment_id,
                filenames=[filename],  # New model uses JSON array
                capture_type=capture_type,
                capture_metadata=capture_metadata,  # Include session timing
                created_at=timestamp
            )
            
            db.add(capture)
            db.commit()
            return capture

    @staticmethod
    def get_session_captures(session_id: str) -> List[Dict[str, Any]]:
        """Get all captures for a session with new model structure"""
        with get_session() as db:
            captures = db.query(CameraCapture).filter_by(
                session_id=session_id
            ).order_by(CameraCapture.created_at).all()
            
            upload_path = CameraCaptureService.get_upload_path()
            
            result = []
            for capture in captures:
                capture_data = {
                    'id': capture.id,
                    'filename': capture.filenames[0] if capture.filenames else '',  # Take first filename for backward compatibility
                    'full_path': os.path.join(upload_path, capture.filenames[0]) if capture.filenames else '',
                    'url': f"/assessment/camera/file/{capture.filenames[0]}" if capture.filenames else '',
                    'timestamp': capture.created_at,
                    'capture_type': capture.capture_type.lower(),
                    'assessment_id': capture.assessment_id,
                    'assessment_type': capture.capture_type.lower()
                }
                
                # Include session_time from metadata if available
                if capture.capture_metadata and 'session_time' in capture.capture_metadata:
                    capture_data['session_time'] = capture.capture_metadata['session_time']
                else:
                    # Fallback: calculate session_time from timestamp
                    capture_data['session_time'] = SessionTimingService.get_session_time(session_id, capture.created_at)
                
                result.append(capture_data)
            
            return result

    @staticmethod
    def get_captures_by_phq_response(phq_response_id: str) -> List[CameraCapture]:
        """Get captures linked to specific PHQ response"""
        with get_session() as db:
            return db.query(CameraCapture).filter(
                CameraCapture.assessment_id == phq_response_id,
                CameraCapture.capture_type == 'PHQ'
            ).order_by(CameraCapture.created_at).all()

    @staticmethod
    def get_captures_by_llm_conversation(llm_conversation_id: str) -> List[CameraCapture]:
        """Get captures linked to specific LLM conversation"""
        with get_session() as db:
            return db.query(CameraCapture).filter(
                CameraCapture.assessment_id == llm_conversation_id,
                CameraCapture.capture_type == 'LLM'
            ).order_by(CameraCapture.created_at).all()

    @staticmethod
    def get_camera_settings_for_session(session_id: str) -> Optional[CameraSettings]:
        """Get active camera settings for the session with fallback to current active settings"""
        with get_session() as db:
            # Get session to find camera_settings_id
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                return None
            
            camera_settings = None
            
            # Try to get linked camera settings first
            if session.camera_settings_id:
                camera_settings = db.query(CameraSettings).filter_by(
                    id=session.camera_settings_id,
                    is_active=True
                ).first()
            
            # Fallback: get current active camera settings if session has none or invalid ones
            if not camera_settings:
                camera_settings = db.query(CameraSettings).filter_by(is_active=True).first()
                
                # Update session to link to current active settings (fix broken sessions)
                if camera_settings and camera_settings.recording_mode in ['INTERVAL', 'EVENT_DRIVEN']:
                    session.camera_settings_id = camera_settings.id
                    db.commit()
            
            # Validate recording mode before returning
            if camera_settings and camera_settings.recording_mode in ['INTERVAL', 'EVENT_DRIVEN']:
                return camera_settings
            
            return None

    @staticmethod
    def create_settings_snapshot(settings: CameraSettings) -> Dict[str, Any]:
        """Create snapshot of camera settings for capture metadata with dynamic upload path"""
        if not settings:
            return {}
            
        return {
            'recording_mode': settings.recording_mode,
            'interval_seconds': settings.interval_seconds,
            'resolution': settings.resolution,
            'upload_path': CameraCaptureService.get_upload_path(),  # Dynamic path from current_app.media_save
            'capture_on_button_click': settings.capture_on_button_click,
            'capture_on_message_send': settings.capture_on_message_send,
            'capture_on_question_start': settings.capture_on_question_start
        }

    # Validation removed - frontend handles all capture logic in "sent mode"

    @staticmethod
    def cleanup_old_captures(retention_days: int = 30):
        """Clean up old capture files and database records"""
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        upload_path = CameraCaptureService.get_upload_path()
        
        with get_session() as db:
            old_captures = db.query(CameraCapture).filter(
                CameraCapture.created_at < cutoff_date
            ).all()
            for capture in old_captures:
                # Delete physical files with error handling (new model uses JSON array)
                for filename in capture.filenames:
                    file_path = os.path.join(upload_path, filename)
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        print(f"Failed to delete camera capture file {filename}: {e}")
                db.delete(capture)
            db.commit()
            return len(old_captures)

    @staticmethod
    def cleanup_session_captures(session_id: str):
        """Clean up all captures for a specific session (files + DB records)"""
        upload_path = CameraCaptureService.get_upload_path()
        deleted_count = 0
        
        with get_session() as db:
            session_captures = db.query(CameraCapture).filter_by(
                session_id=session_id
            ).all()
            
            for capture in session_captures:
                # Delete physical files with error handling (new model uses JSON array)
                for filename in capture.filenames:
                    file_path = os.path.join(upload_path, filename)
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            deleted_count += 1
                    except Exception as e:
                        print(f"Failed to delete camera capture file {filename}: {e}")
                
                # DB record will be auto-deleted by CASCADE foreign key
            
            return deleted_count

    @staticmethod
    def cleanup_phq_captures(phq_response_id: str):
        """Clean up captures for a specific PHQ response ID"""
        upload_path = CameraCaptureService.get_upload_path()
        
        with get_session() as db:
            phq_captures = db.query(CameraCapture).filter(
                CameraCapture.assessment_id == phq_response_id,
                CameraCapture.capture_type == 'PHQ'
            ).all()
            
            for capture in phq_captures:
                # Delete physical files with error handling (new model uses JSON array)
                for filename in capture.filenames:
                    file_path = os.path.join(upload_path, filename)
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        print(f"Failed to delete camera capture file {filename}: {e}")
            
            return len(phq_captures)

    @staticmethod
    def cleanup_llm_captures(llm_conversation_id: str):
        """Clean up captures for a specific LLM conversation ID"""  
        upload_path = CameraCaptureService.get_upload_path()
        
        with get_session() as db:
            llm_captures = db.query(CameraCapture).filter(
                CameraCapture.assessment_id == llm_conversation_id,
                CameraCapture.capture_type == 'LLM'
            ).all()
            
            for capture in llm_captures:
                # Delete physical files with error handling (new model uses JSON array)
                for filename in capture.filenames:
                    file_path = os.path.join(upload_path, filename)
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        print(f"Failed to delete camera capture file {filename}: {e}")
            
            return len(llm_captures)

    @staticmethod
    def bulk_link_captures_to_phq(session_id: str, phq_response_id: str) -> int:
        """Bulk link unlinked session captures to PHQ assessment"""
        with get_session() as db:
            # Find captures that are only linked to session (no specific assessment)
            unlinked_captures = db.query(CameraCapture).filter(
                CameraCapture.session_id == session_id,
                CameraCapture.assessment_id == session_id  # Unlinked captures have session_id as assessment_id
            ).all()
            
            linked_count = 0
            for capture in unlinked_captures:
                capture.assessment_id = phq_response_id
                capture.capture_type = 'PHQ'
                linked_count += 1
            
            db.commit()
            return linked_count

    @staticmethod
    def bulk_link_captures_to_llm(session_id: str, llm_conversation_id: str) -> int:
        """Bulk link unlinked session captures to LLM assessment"""
        with get_session() as db:
            # Find captures that are only linked to session (no specific assessment)
            unlinked_captures = db.query(CameraCapture).filter(
                CameraCapture.session_id == session_id,
                CameraCapture.assessment_id == session_id  # Unlinked captures have session_id as assessment_id
            ).all()
            
            linked_count = 0
            for capture in unlinked_captures:
                capture.assessment_id = llm_conversation_id
                capture.capture_type = 'LLM'
                linked_count += 1
            
            db.commit()
            return linked_count