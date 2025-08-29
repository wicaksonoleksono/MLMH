# app/services/camera/cameraCaptureService.py
import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from flask import current_app
from ...db import get_session
from ...model.assessment.sessions import CameraCapture, AssessmentSession
from ...model.admin.camera import CameraSettings


class CameraCaptureService:
    """Service for handling camera capture operations with settings integration"""

    @staticmethod
    def get_upload_path() -> str:
        """Get the upload directory path dynamically"""
        return os.path.join(current_app.root_path, 'uploads')

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
            print(f"❌ Failed to delete capture file {filename}: {e}")
            return False

    @staticmethod
    def generate_filename(timestamp: datetime, assessment_type: str, session_uuid: str) -> str:
        """Generate filename: {timestamp}_{type}_{session_uuid_short}.jpg"""
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
        short_uuid = session_uuid[:8]
        return f"{timestamp_str}_{assessment_type}_{short_uuid}.jpg"

    @staticmethod
    def save_capture(
        assessment_session_id: str,
        file_data: bytes,
        capture_trigger: str,
        phq_session_uuid: Optional[str] = None,
        llm_session_uuid: Optional[str] = None,
        camera_settings_snapshot: Optional[Dict[str, Any]] = None
    ) -> CameraCapture:
        """Save camera capture file and database record"""
        
        # Ensure upload directory exists
        upload_path = CameraCaptureService.ensure_upload_directory()
        
        # Generate filename based on context
        timestamp = datetime.utcnow()
        assessment_type = 'phq' if phq_session_uuid else 'llm' if llm_session_uuid else 'general'
        target_uuid = phq_session_uuid or llm_session_uuid or assessment_session_id
        
        filename = CameraCaptureService.generate_filename(timestamp, assessment_type, target_uuid)
        full_path = os.path.join(upload_path, filename)
        
        # Save file to disk
        with open(full_path, 'wb') as f:
            f.write(file_data)
        
        file_size = len(file_data)
        
        # Save database record
        with get_session() as db:
            capture = CameraCapture(
                assessment_session_id=assessment_session_id,
                phq_session_uuid=phq_session_uuid,
                llm_session_uuid=llm_session_uuid,
                filename=filename,
                file_size_bytes=file_size,
                capture_trigger=capture_trigger,
                timestamp=timestamp,
                camera_settings_snapshot=camera_settings_snapshot
            )
            
            db.add(capture)
            db.commit()
            return capture

    @staticmethod
    def get_session_captures(assessment_session_id: str) -> List[Dict[str, Any]]:
        """Get all captures for a session with reconstructed paths"""
        with get_session() as db:
            captures = db.query(CameraCapture).filter_by(
                assessment_session_id=assessment_session_id
            ).order_by(CameraCapture.timestamp).all()
            
            upload_path = CameraCaptureService.get_upload_path()
            
            return [{
                'id': capture.id,
                'filename': capture.filename,
                'full_path': os.path.join(upload_path, capture.filename),
                'url': f"/assessment/camera/file/{capture.filename}",
                'timestamp': capture.timestamp,
                'capture_trigger': capture.capture_trigger,
                'file_size_bytes': capture.file_size_bytes,
                'phq_session_uuid': capture.phq_session_uuid,
                'llm_session_uuid': capture.llm_session_uuid,
                'assessment_type': 'phq' if capture.phq_session_uuid else 'llm' if capture.llm_session_uuid else 'general'
            } for capture in captures]

    @staticmethod
    def get_captures_by_phq_session(phq_session_uuid: str) -> List[CameraCapture]:
        """Get captures linked to specific PHQ session"""
        with get_session() as db:
            return db.query(CameraCapture).filter_by(
                phq_session_uuid=phq_session_uuid
            ).order_by(CameraCapture.timestamp).all()

    @staticmethod
    def get_captures_by_llm_session(llm_session_uuid: str) -> List[CameraCapture]:
        """Get captures linked to specific LLM session"""
        with get_session() as db:
            return db.query(CameraCapture).filter_by(
                llm_session_uuid=llm_session_uuid
            ).order_by(CameraCapture.timestamp).all()

    @staticmethod
    def get_camera_settings_for_session(session_id: str) -> Optional[CameraSettings]:
        """Get active camera settings for the session"""
        with get_session() as db:
            # Get session to find camera_settings_id
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session or not session.camera_settings_id:
                return None
            
            # Get camera settings
            return db.query(CameraSettings).filter_by(
                id=session.camera_settings_id,
                is_active=True
            ).first()

    @staticmethod
    def create_settings_snapshot(settings: CameraSettings) -> Dict[str, Any]:
        """Create snapshot of camera settings for capture metadata with dynamic upload path"""
        if not settings:
            return {}
            
        return {
            'setting_name': settings.setting_name,
            'recording_mode': settings.recording_mode,
            'interval_seconds': settings.interval_seconds,
            'resolution': settings.resolution,
            'upload_path': CameraCaptureService.get_upload_path(),  # Dynamic path from current_app.root_path
            'capture_on_button_click': settings.capture_on_button_click,
            'capture_on_message_send': settings.capture_on_message_send,
            'capture_on_question_start': settings.capture_on_question_start
        }

    @staticmethod
    def should_capture_on_trigger(settings: CameraSettings, trigger: str) -> bool:
        """Check if capture should happen based on settings and trigger"""
        if not settings:
            return False
            
        if settings.recording_mode == 'INTERVAL':
            return trigger == 'INTERVAL'
        elif settings.recording_mode == 'EVENT_DRIVEN':
            trigger_map = {
                'BUTTON_CLICK': settings.capture_on_button_click,
                'MESSAGE_SEND': settings.capture_on_message_send
            }
            return trigger_map.get(trigger, False)
        
        return False

    @staticmethod
    def cleanup_old_captures(retention_days: int = 30):
        """Clean up old capture files and database records"""
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        upload_path = CameraCaptureService.get_upload_path()
        
        with get_session() as db:
            old_captures = db.query(CameraCapture).filter(
                CameraCapture.timestamp < cutoff_date
            ).all()
            
            for capture in old_captures:
                # Delete file if it exists
                file_path = os.path.join(upload_path, capture.filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                # Delete database record
                db.delete(capture)
            
            db.commit()
            return len(old_captures)

    @staticmethod
    def cleanup_session_captures(assessment_session_id: str):
        """Clean up all captures for a specific session (files + DB records)"""
        upload_path = CameraCaptureService.get_upload_path()
        
        with get_session() as db:
            session_captures = db.query(CameraCapture).filter_by(
                assessment_session_id=assessment_session_id
            ).all()
            
            for capture in session_captures:
                # Delete physical file
                file_path = os.path.join(upload_path, capture.filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                # DB record will be auto-deleted by CASCADE foreign key
            
            return len(session_captures)

    @staticmethod
    def cleanup_phq_captures(phq_session_uuid: str):
        """Clean up captures for a specific PHQ session UUID"""
        upload_path = CameraCaptureService.get_upload_path()
        
        with get_session() as db:
            phq_captures = db.query(CameraCapture).filter_by(
                phq_session_uuid=phq_session_uuid
            ).all()
            
            for capture in phq_captures:
                # Delete physical file
                file_path = os.path.join(upload_path, capture.filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            return len(phq_captures)

    @staticmethod
    def cleanup_llm_captures(llm_session_uuid: str):
        """Clean up captures for a specific LLM session UUID"""  
        upload_path = CameraCaptureService.get_upload_path()
        
        with get_session() as db:
            llm_captures = db.query(CameraCapture).filter_by(
                llm_session_uuid=llm_session_uuid
            ).all()
            
            for capture in llm_captures:
                # Delete physical file
                file_path = os.path.join(upload_path, capture.filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            return len(llm_captures)