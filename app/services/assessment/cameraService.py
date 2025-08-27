# app/services/assessment/cameraService.py
from typing import List, Dict, Any, Optional
import os
from datetime import datetime
from ...model.assessment.sessions import AssessmentSession, CameraCapture
from ...model.admin.camera import CameraSettings
from ...db import get_session


class CameraService:
    """Service for handling camera captures during assessment sessions with CRUD operations"""
    
    @staticmethod
    def create_capture(
        session_id: int,
        capture_sequence: int,
        image_path: str,
        thumbnail_path: Optional[str] = None,
        image_metadata: Optional[Dict[str, Any]] = None,
        face_detection_results: Optional[Dict[str, Any]] = None,
        emotion_analysis: Optional[Dict[str, Any]] = None
    ) -> CameraCapture:
        """Create a new camera capture record"""
        with get_session() as db:
            # Get file size if file exists
            file_size = None
            if os.path.exists(image_path):
                file_size = os.path.getsize(image_path)
            
            # Extract image dimensions from metadata if available
            dimensions = None
            if image_metadata and 'width' in image_metadata and 'height' in image_metadata:
                dimensions = {
                    'width': image_metadata['width'],
                    'height': image_metadata['height']
                }
            
            capture = CameraCapture(
                session_id=session_id,
                capture_sequence=capture_sequence,
                image_path=image_path,
                thumbnail_path=thumbnail_path,
                image_metadata=image_metadata,
                face_detection_results=face_detection_results,
                emotion_analysis=emotion_analysis,
                file_size_bytes=file_size,
                image_dimensions=dimensions
            )
            
            db.add(capture)
            db.commit()
            return capture
    
    @staticmethod
    def get_session_captures(session_id: int) -> List[CameraCapture]:
        """Get all camera captures for a session"""
        with get_session() as db:
            return db.query(CameraCapture).filter_by(session_id=session_id).order_by(CameraCapture.capture_sequence).all()
    
    @staticmethod
    def get_capture_by_id(capture_id: int) -> Optional[CameraCapture]:
        """Get a specific camera capture by ID"""
        with get_session() as db:
            return db.query(CameraCapture).filter_by(id=capture_id).first()
    
    @staticmethod
    def update_capture(capture_id: int, updates: Dict[str, Any]) -> CameraCapture:
        """Update a camera capture record"""
        with get_session() as db:
            capture = db.query(CameraCapture).filter_by(id=capture_id).first()
            if not capture:
                raise ValueError(f"Camera capture with ID {capture_id} not found")
            
            for key, value in updates.items():
                if hasattr(capture, key):
                    setattr(capture, key, value)
            
            # Update file size if image path changed
            if 'image_path' in updates and os.path.exists(updates['image_path']):
                capture.file_size_bytes = os.path.getsize(updates['image_path'])
            
            db.commit()
            return capture
    
    @staticmethod
    def delete_capture(capture_id: int, delete_files: bool = False) -> bool:
        """Delete a camera capture record and optionally the files"""
        with get_session() as db:
            capture = db.query(CameraCapture).filter_by(id=capture_id).first()
            if not capture:
                raise ValueError(f"Camera capture with ID {capture_id} not found")
            
            # Store file paths before deletion
            image_path = capture.image_path
            thumbnail_path = capture.thumbnail_path
            
            db.delete(capture)
            db.commit()
            
            # Delete physical files if requested
            if delete_files:
                if image_path and os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except OSError:
                        pass  # File might already be deleted
                
                if thumbnail_path and os.path.exists(thumbnail_path):
                    try:
                        os.remove(thumbnail_path)
                    except OSError:
                        pass  # File might already be deleted
            
            return True
    
    @staticmethod
    def validate_capture_files(session_id: int) -> Dict[str, Any]:
        """Validate that all capture files exist and are accessible"""
        with get_session() as db:
            captures = db.query(CameraCapture).filter_by(session_id=session_id).all()
            
            validation_results = {
                "total_captures": len(captures),
                "valid_files": 0,
                "missing_files": 0,
                "invalid_captures": []
            }
            
            for capture in captures:
                if capture.file_exists:
                    validation_results["valid_files"] += 1
                else:
                    validation_results["missing_files"] += 1
                    validation_results["invalid_captures"].append({
                        "capture_id": capture.id,
                        "sequence": capture.capture_sequence,
                        "image_path": capture.image_path,
                        "issue": "File not found"
                    })
            
            validation_results["all_valid"] = validation_results["missing_files"] == 0
            
            return validation_results
    
    @staticmethod
    def get_capture_statistics(session_id: int) -> Dict[str, Any]:
        """Get statistics about camera captures for a session"""
        with get_session() as db:
            captures = db.query(CameraCapture).filter_by(session_id=session_id).all()
            
            if not captures:
                return {"total_captures": 0}
            
            total_size = sum(c.file_size_bytes for c in captures if c.file_size_bytes)
            valid_captures = sum(1 for c in captures if c.is_valid_capture)
            
            # Calculate time span
            first_capture = min(captures, key=lambda x: x.capture_timestamp)
            last_capture = max(captures, key=lambda x: x.capture_timestamp)
            time_span = (last_capture.capture_timestamp - first_capture.capture_timestamp).total_seconds()
            
            # Emotion analysis summary
            emotions_detected = 0
            faces_detected = 0
            
            for capture in captures:
                if capture.emotion_analysis:
                    emotions_detected += 1
                if capture.face_detection_results:
                    faces_detected += 1
            
            return {
                "total_captures": len(captures),
                "valid_captures": valid_captures,
                "invalid_captures": len(captures) - valid_captures,
                "total_file_size_mb": round(total_size / (1024 * 1024), 2) if total_size else 0,
                "time_span_seconds": time_span,
                "average_interval_seconds": time_span / (len(captures) - 1) if len(captures) > 1 else 0,
                "captures_with_emotions": emotions_detected,
                "captures_with_faces": faces_detected,
                "first_capture_time": first_capture.capture_timestamp.isoformat(),
                "last_capture_time": last_capture.capture_timestamp.isoformat()
            }
    
    @staticmethod
    def bulk_create_captures(session_id: int, captures_data: List[Dict[str, Any]]) -> List[CameraCapture]:
        """Create multiple camera captures at once"""
        created_captures = []
        
        for i, capture_data in enumerate(captures_data):
            capture = CameraService.create_capture(
                session_id=session_id,
                capture_sequence=capture_data.get('capture_sequence', i + 1),
                image_path=capture_data['image_path'],
                thumbnail_path=capture_data.get('thumbnail_path'),
                image_metadata=capture_data.get('image_metadata'),
                face_detection_results=capture_data.get('face_detection_results'),
                emotion_analysis=capture_data.get('emotion_analysis')
            )
            created_captures.append(capture)
        
        return created_captures
    
    @staticmethod
    def get_session_camera_settings(session_id: int) -> Optional[CameraSettings]:
        """Get the camera settings used for a specific session"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            return session.camera_settings
    
    @staticmethod
    def cleanup_orphaned_files(session_id: int, dry_run: bool = True) -> Dict[str, Any]:
        """Clean up orphaned camera files (files without database records)"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            # Get camera settings to determine storage path
            camera_settings = session.camera_settings
            storage_path = camera_settings.storage_path
            
            # Get all capture records
            captures = db.query(CameraCapture).filter_by(session_id=session_id).all()
            recorded_files = {c.image_path for c in captures}
            
            if captures and captures[0].thumbnail_path:
                recorded_files.update({c.thumbnail_path for c in captures if c.thumbnail_path})
            
            # Find files in storage directory
            orphaned_files = []
            total_size = 0
            
            if os.path.exists(storage_path):
                for root, dirs, files in os.walk(storage_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if file_path not in recorded_files:
                            file_size = os.path.getsize(file_path)
                            orphaned_files.append({
                                "path": file_path,
                                "size_bytes": file_size
                            })
                            total_size += file_size
                            
                            if not dry_run:
                                try:
                                    os.remove(file_path)
                                except OSError:
                                    pass
            
            return {
                "orphaned_files_found": len(orphaned_files),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "files_cleaned": len(orphaned_files) if not dry_run else 0,
                "dry_run": dry_run,
                "orphaned_files": orphaned_files[:10]  # Show first 10 files
            }