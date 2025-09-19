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
    def get_storage_path_for_session(session_id: str) -> Optional[str]:
        """Get storage path from camera settings for session"""
        from ..camera.cameraCaptureService import CameraCaptureService
        settings = CameraCaptureService.get_camera_settings_for_session(session_id)
        return settings.storage_path if settings else None

    @staticmethod
    def save_image_locally(
        session_id: str, 
        file_data: bytes, 
        timestamp: Optional[str] = None
    ) -> str:
        """Save image file locally and return filename - NO DATABASE WRITES"""
        
        # Get storage path from camera settings
        storage_path = CameraStorageService.get_storage_path_for_session(session_id)
        if not storage_path:
            # Fallback to current_app.media_save if no settings found
            storage_path = current_app.media_save
        
        # Ensure directory exists
        os.makedirs(storage_path, exist_ok=True)
        
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
        if not timestamp:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        short_uuid = uuid.uuid4().hex[:8]
        
        if username and session_number:
            # Clean username (remove spaces, special chars)
            clean_username = "".join(c for c in username if c.isalnum() or c in ('_', '-')).lower()
            filename = f"{clean_username}_s{session_number}_{timestamp}_{short_uuid}.jpg"
        else:
            # Fallback to old format
            filename = f"{uuid.uuid4().hex}_{timestamp}.jpg"
        file_path = os.path.join(storage_path, filename)
        
        # Save file
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        return filename


    @staticmethod
    def create_batch_capture_with_assessment_id(
        session_id: str,
        assessment_id: str,
        filenames: List[str],
        capture_type: str,  # 'PHQ' or 'LLM'
        capture_metadata: Optional[Dict[str, Any]] = None
    ) -> CameraCapture:
        """Create CameraCapture record with assessment_id directly - ASSESSMENT-FIRST APPROACH"""
        with get_session() as db:
            # Create batch record with assessment_id already set
            capture = CameraCapture(
                session_id=session_id,
                assessment_id=assessment_id,  # Set immediately
                filenames=filenames,
                capture_type=capture_type.upper(),
                capture_metadata=capture_metadata or {},
                created_at=datetime.now()
            )
            
            db.add(capture)
            db.commit()
            db.refresh(capture)
            
            print(f"Created batch capture with assessment_id {assessment_id}: {filenames} files")
            return capture

    @staticmethod
    def create_batch_capture(
        session_id: str,
        filenames: List[str],
        capture_type: str,  # 'PHQ' or 'LLM'
        capture_metadata: Optional[Dict[str, Any]] = None
    ) -> CameraCapture:
        """Create single CameraCapture record with all filenames and metadata - BATCH APPROACH"""
        # Log to file for debugging
        import logging
        logging.basicConfig(filename='/tmp/camera_debug.log', level=logging.DEBUG, 
                          format='%(asctime)s - %(message)s')
        
        logging.debug(f"CREATE BATCH DEBUG:")
        logging.debug(f"   session_id: {session_id}")
        logging.debug(f"   filenames: {filenames} (type: {type(filenames)}, length: {len(filenames) if filenames else 0})")
        logging.debug(f"   capture_type: {capture_type}")
        logging.debug(f"   capture_metadata: {capture_metadata}")
        
        with get_session() as db:
            # Create new batch record
            capture = CameraCapture(
                session_id=session_id,
                assessment_id=None,  # Null until linked to PHQ/LLM record (camera-first approach)
                filenames=filenames,
                capture_type=capture_type.upper(),
                capture_metadata=capture_metadata or {},
                created_at=datetime.now()
            )
            
            db.add(capture)
            db.commit()
            db.refresh(capture)
            
            logging.debug(f"AFTER DB SAVE:")
            logging.debug(f"   capture.id: {capture.id}")
            logging.debug(f"   capture.filenames: {capture.filenames} (type: {type(capture.filenames)})")
            logging.debug(f"   capture.capture_type: {capture.capture_type}")
            
            # Also print to console for immediate feedback
            print(f"DEBUG: Created camera batch {capture.id} with {capture.filenames} files")
            
            return capture

    @staticmethod
    def link_session_captures_to_assessment(
        session_id: str,
        assessment_id: str,
        assessment_type: str
    ) -> CameraCapture:
        """Link existing unlinked session captures to assessment - INCREMENTAL APPROACH"""
        with get_session() as db:
            # Find unlinked captures for this session
            capture = db.query(CameraCapture).filter_by(
                session_id=session_id,
                assessment_id=None
            ).first()
            
            if capture:
                # Link to assessment
                capture.assessment_id = assessment_id
                capture.capture_type = assessment_type.upper()
                
                # Update metadata
                capture.capture_metadata = capture.capture_metadata or {}
                capture.capture_metadata['linked_at'] = datetime.now().isoformat()
                capture.capture_metadata['linked_to'] = f"{assessment_type}_{assessment_id}"
                
                # Force SQLAlchemy to detect JSON column changes
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(capture, 'capture_metadata')
                
                db.commit()
                db.refresh(capture)
                
                print(f"Linked capture {capture.id} to {assessment_type} assessment {assessment_id}: {capture.filenames} files")
                return capture
            return None

    @staticmethod
    def update_batch_capture(
        capture_id: str,
        assessment_id: str,
        capture_type: str
    ) -> CameraCapture:
        """Link batch capture to assessment record"""
        with get_session() as db:
            capture = db.query(CameraCapture).filter_by(id=capture_id).first()
            if capture:
                capture.assessment_id = assessment_id
                capture.capture_type = capture_type.upper()
                db.commit()
                db.refresh(capture)
                return capture
            return None

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
                import logging
                logging.debug(f"CLEANUP - Processing capture {capture.id}: filenames={capture.filenames}, type={type(capture.filenames)}")
                print(f"CLEANUP: Processing capture {capture.id} with {capture.filenames} files")
                if capture.filenames and isinstance(capture.filenames, list):
                    for filename in capture.filenames:
                        if not filename:  # Skip null/empty filenames
                            continue
                        file_path = os.path.join(static_path, filename)
                        logging.debug(f"   Trying to delete: {file_path}, exists: {os.path.exists(file_path)}")
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                                deleted_count += 1
                                logging.debug(f"   Successfully deleted: {filename}")
                            except Exception as e:
                                logging.debug(f"   Warning: Failed to delete file {filename}: {e}")
                        else:
                            logging.debug(f"   File not found: {file_path}")
                else:
                    logging.debug(f"   No valid filenames found for capture {capture.id}: {capture.filenames}")
                db.delete(capture)
            db.commit()
            return deleted_count

    @staticmethod
    def add_filename_with_assessment_id(
        session_id: str,
        assessment_id: str,
        filename: str,
        trigger: str,
        assessment_type: str,
        assessment_timing: Optional[Dict[str, int]] = None
    ) -> CameraCapture:
        """Add filename incrementally to assessment-linked capture record - PUT-style with incremental metadata"""
        
        with get_session() as db:
            # Check if we already have a capture record for this assessment
            capture = db.query(CameraCapture).filter_by(
                session_id=session_id,
                assessment_id=assessment_id,
                capture_type=assessment_type.upper()
            ).first()
            
            # Get current timestamp for this specific capture
            current_time = datetime.now()
            timestamp_iso = current_time.isoformat()
            
            if not capture:
                # Create new capture record with assessment_id and first filename
                capture = CameraCapture(
                    session_id=session_id,
                    assessment_id=assessment_id,  # Link to assessment immediately
                    filenames=[filename],  # Start with first filename
                    capture_type=assessment_type.upper(),
                    capture_metadata={
                        'triggers': [{'trigger': trigger, 'timestamp': timestamp_iso}],
                        'capture_count': 1,
                        'started_at': timestamp_iso,
                        'last_updated': timestamp_iso,
                        'created_with_assessment': True
                    },
                    created_at=current_time
                )
                
                db.add(capture)
            else:
                # Incrementally add filename and update metadata
                filenames_copy = list(capture.filenames)
                filenames_copy.append(filename)
                capture.filenames = filenames_copy
                
                # Update metadata incrementally
                current_metadata = capture.capture_metadata or {}
                
                # Add trigger with timestamp
                triggers = current_metadata.get('triggers', [])
                triggers.append({'trigger': trigger, 'timestamp': timestamp_iso})
                
                # Update metadata
                capture.capture_metadata = {
                    **current_metadata,
                    'triggers': triggers,
                    'capture_count': len(filenames_copy),
                    'last_updated': timestamp_iso,
                    'total_duration_seconds': (current_time - datetime.fromisoformat(current_metadata.get('started_at', timestamp_iso))).total_seconds()
                }
                
                # Add timing if provided
                if assessment_timing:
                    if 'capture_timings' not in capture.capture_metadata:
                        capture.capture_metadata['capture_timings'] = []
                    capture.capture_metadata['capture_timings'].append({
                        'filename': filename,
                        'timing': assessment_timing,
                        'timestamp': timestamp_iso
                    })
                
                # Force SQLAlchemy to detect JSON field changes
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(capture, 'filenames')
                flag_modified(capture, 'capture_metadata')
                
                capture.updated_at = current_time
            
            db.commit()
            db.refresh(capture)
            
            return capture
        