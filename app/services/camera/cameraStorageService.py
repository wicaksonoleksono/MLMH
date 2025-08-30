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
        phq_response_id: Optional[str] = None,
        llm_conversation_id: Optional[str] = None
    ) -> CameraCapture:
        """Save image directly to uploads/ with minimal DB record"""
        
        static_path = CameraStorageService.ensure_uploads_directory()
        
        # Generate simple filename
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        filename = f"{uuid.uuid4().hex}_{timestamp}.jpg"
        file_path = os.path.join(static_path, filename)
        
        # Save file
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        # Create simple DB record
        with get_session() as db:
            capture = CameraCapture(
                assessment_session_id=session_id,
                phq_response_id=phq_response_id,
                llm_conversation_id=llm_conversation_id,
                filename=filename,
                file_size_bytes=len(file_data),
                capture_trigger=trigger,
                timestamp=datetime.utcnow()
            )
            
            db.add(capture)
            db.commit()
            return capture

    @staticmethod
    def get_session_captures(session_id: str) -> List[CameraCapture]:
        """Get all captures for session"""
        with get_session() as db:
            return db.query(CameraCapture).filter_by(
                assessment_session_id=session_id
            ).order_by(CameraCapture.timestamp).all()

    @staticmethod
    def get_phq_captures(phq_response_id: str) -> List[CameraCapture]:
        """Get captures linked to PHQ response (cascading FK)"""
        with get_session() as db:
            return db.query(CameraCapture).filter_by(
                phq_response_id=phq_response_id
            ).order_by(CameraCapture.timestamp).all()

    @staticmethod
    def get_llm_captures(llm_conversation_id: str) -> List[CameraCapture]:
        """Get captures linked to LLM conversation (cascading FK)"""
        with get_session() as db:
            return db.query(CameraCapture).filter_by(
                llm_conversation_id=llm_conversation_id
            ).order_by(CameraCapture.timestamp).all()

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
                assessment_session_id=session_id
            ).all()
            
            for capture in captures:
                # Delete physical file
                file_path = os.path.join(static_path, capture.filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
                
                # DB record will cascade delete
            
            return deleted_count