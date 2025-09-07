# app/services/camera/cameraStorageService.py
import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from flask import current_app
from ...db import get_session
from ...model.assessment.sessions import CameraCapture


class CameraStorageService:
    """Simple unified camera storage - files in uploads/, minimal DB tracking"""

    @staticmethod
    def get_uploads_path() -> str:
        """Get static directory path for camera files"""
        return current_app.media_save

    @staticmethod
    def ensure_uploads_directory() -> str:
        """Ensure static directory exists (already created in __init__.py)"""
        return current_app.media_save

    @staticmethod
    def save_image(
        session_id: str, 
        file_data: bytes, 
        trigger: str,
        assessment_id: Optional[str] = None,
        capture_type: str = 'GENERAL'
    ) -> CameraCapture:
        """Save image directly to uploads/ with minimal DB record"""
        
        static_path = CameraStorageService.ensure_uploads_directory()
        
        # Get session info for filename
        username = None
        session_number = None
        with get_session() as db:
            from ...model.assessment.sessions import AssessmentSession
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if session and session.user:
                username = session.user.uname
                session_number = session.session_number
        
        # Generate filename with username and session info
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        short_uuid = uuid.uuid4().hex[:8]
        
        if username and session_number:
            # Clean username (remove spaces, special chars)
            clean_username = "".join(c for c in username if c.isalnum() or c in ('_', '-')).lower()
            filename = f"{clean_username}_s{session_number}_{timestamp}_{short_uuid}.jpg"
        else:
            # Fallback to old format
            filename = f"{uuid.uuid4().hex}_{timestamp}.jpg"
        file_path = os.path.join(static_path, filename)
        
        # Save file
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        # Create DB record using new model structure
        with get_session() as db:
            capture = CameraCapture(
                session_id=session_id,
                assessment_id=assessment_id,
                filenames=[filename],  # New model uses JSON array
                capture_type=capture_type,
                created_at=datetime.utcnow()
            )
            
            db.add(capture)
            db.commit()
            db.refresh(capture)  # Ensure we get the auto-generated ID
            return capture

    @staticmethod
    def get_session_captures(session_id: str) -> List[CameraCapture]:
        """Get all captures for session"""
        with get_session() as db:
            return db.query(CameraCapture).filter_by(
                session_id=session_id
            ).order_by(CameraCapture.created_at).all()

    @staticmethod
    def get_phq_captures(assessment_id: str) -> List[CameraCapture]:
        """Get captures linked to PHQ assessment"""
        with get_session() as db:
            return db.query(CameraCapture).filter(
                CameraCapture.assessment_id == assessment_id,
                CameraCapture.capture_type == 'PHQ'
            ).order_by(CameraCapture.created_at).all()

    @staticmethod
    def get_llm_captures(assessment_id: str) -> List[CameraCapture]:
        """Get captures linked to LLM assessment"""
        with get_session() as db:
            return db.query(CameraCapture).filter(
                CameraCapture.assessment_id == assessment_id,
                CameraCapture.capture_type == 'LLM'
            ).order_by(CameraCapture.created_at).all()

    @staticmethod
    def get_capture_file_path(filename: str) -> str:
        """Get full path for a capture file"""
        static_path = CameraStorageService.get_uploads_path()
        return os.path.join(static_path, filename)

    @staticmethod
    def cleanup_session_captures(session_id: str) -> int:
        """Delete all captures for session (files + DB records)"""
        static_path = CameraStorageService.get_uploads_path()
        deleted_count = 0
        
        with get_session() as db:
            captures = db.query(CameraCapture).filter_by(
                session_id=session_id
            ).all()
            
            for capture in captures:
                # Delete physical files (new model has multiple filenames)
                for filename in capture.filenames:
                    file_path = os.path.join(static_path, filename)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        deleted_count += 1
                
                # DB record will cascade delete
            
            return deleted_count