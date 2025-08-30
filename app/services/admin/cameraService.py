# app/services/admin/cameraService.py
from typing import List, Optional, Dict, Any
from flask import current_app
from sqlalchemy import and_
from ...model.admin.camera import CameraSettings
from ...db import get_session


class CameraService:
    """Camera service for managing camera recording settings"""

    @staticmethod
    def get_settings() -> List[Dict[str, Any]]:
        """Get all camera settings"""
        with get_session() as db:
            settings = db.query(CameraSettings).filter(CameraSettings.is_active == True).all()
            return [{
                'id': setting.id,
                'recording_mode': setting.recording_mode,
                'interval_seconds': setting.interval_seconds,
                'resolution': setting.resolution,
                'storage_path': setting.storage_path,
                'capture_on_button_click': setting.capture_on_button_click,
                'capture_on_message_send': setting.capture_on_message_send,
                'capture_on_question_start': setting.capture_on_question_start,
                'is_default': setting.is_default
            } for setting in settings]

    @staticmethod
    def create_settings(recording_mode: str,
                       interval_seconds: Optional[int] = None, resolution: str = "1280x720",
                       capture_on_button_click: bool = True, capture_on_message_send: bool = False,
                       capture_on_question_start: bool = False, is_default: bool = False) -> Dict[str, Any]:
        """Create or update camera settings with mutually exclusive mode enforcement"""
        
        # 🔒 ENFORCE MUTUALLY EXCLUSIVE MODES - NO FUCKED UP DATA!
        if recording_mode not in ['INTERVAL', 'EVENT_DRIVEN']:
            raise ValueError(f"Invalid recording_mode: {recording_mode}. Must be 'INTERVAL' or 'EVENT_DRIVEN'")
        
        # INTERVAL mode validation
        if recording_mode == 'INTERVAL':
            if interval_seconds is None or interval_seconds < 1 or interval_seconds > 60:
                raise ValueError("INTERVAL mode requires interval_seconds between 1-60")
            # Force event-driven settings to False for INTERVAL mode
            capture_on_button_click = False
            capture_on_message_send = False
            capture_on_question_start = False
        
        # EVENT_DRIVEN mode validation  
        elif recording_mode == 'EVENT_DRIVEN':
            if not any([capture_on_button_click, capture_on_message_send, capture_on_question_start]):
                raise ValueError("EVENT_DRIVEN mode requires at least one capture trigger enabled")
            # Force interval to None for EVENT_DRIVEN mode
            interval_seconds = None
        
        with get_session() as db:
            absolute_storage_path=current_app.media_save
            existing = db.query(CameraSettings).filter(CameraSettings.is_default == True).first()
            
            # 🎯 MUTUALLY EXCLUSIVE: Only one mode can be default at a time
            if is_default:
                # Remove default from ALL other settings (ensures only one default)
                db.query(CameraSettings).filter(CameraSettings.is_default == True).update({'is_default': False})
                # Also disable any other active settings to enforce single active mode
                db.query(CameraSettings).filter(
                    CameraSettings.id != (existing.id if existing else -1)
                ).update({'is_active': False})
            
            if existing:
                # Update existing settings
                existing.recording_mode = recording_mode
                existing.interval_seconds = interval_seconds
                existing.resolution = resolution
                existing.storage_path = absolute_storage_path
                existing.capture_on_button_click = capture_on_button_click
                existing.capture_on_message_send = capture_on_message_send
                existing.capture_on_question_start = capture_on_question_start
                existing.is_default = is_default
                settings = existing
            else:
                # Create new settings
                settings = CameraSettings(
                    recording_mode=recording_mode,
                    interval_seconds=interval_seconds,
                    resolution=resolution,
                    storage_path=absolute_storage_path,
                    capture_on_button_click=capture_on_button_click,
                    capture_on_message_send=capture_on_message_send,
                    capture_on_question_start=capture_on_question_start,
                    is_default=is_default
                )
                db.add(settings)
            try:
                settings.validate_mutually_exclusive_modes()
            except ValueError as e:
                raise ValueError(f"Camera settings validation failed: {e}")
            if settings.recording_mode == 'INTERVAL':
                all_fields_valid = (
                    settings.recording_mode and settings.recording_mode.strip() != '' and
                    settings.resolution and settings.resolution.strip() != '' and
                    settings.storage_path and settings.storage_path.strip() != '' and
                    settings.interval_seconds is not None and settings.interval_seconds >= 1
                )
            else:  # EVENT_DRIVEN
                all_fields_valid = (
                    settings.recording_mode and settings.recording_mode.strip() != '' and
                    settings.resolution and settings.resolution.strip() != '' and
                    settings.storage_path and settings.storage_path.strip() != '' and
                    any([settings.capture_on_button_click, settings.capture_on_message_send, settings.capture_on_question_start])
                )
            settings.is_active = all_fields_valid
            db.commit()
            return {
                'id': settings.id,
                'recording_mode': settings.recording_mode,
                'interval_seconds': settings.interval_seconds,
                'resolution': settings.resolution,
                'storage_path': settings.storage_path,
                'capture_on_button_click': settings.capture_on_button_click,
                'capture_on_message_send': settings.capture_on_message_send,
                'capture_on_question_start': settings.capture_on_question_start,
                'is_default': settings.is_default
            }
    @staticmethod
    def update_settings(settings_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update camera settings"""
        with get_session() as db:
            settings = db.query(CameraSettings).filter(
                and_(CameraSettings.id == settings_id, CameraSettings.is_active == True)
            ).first()

            if not settings:
                raise ValueError(f"Camera settings with ID {settings_id} not found")

            if updates.get('is_default'):
                # Remove default from other settings
                db.query(CameraSettings).filter(CameraSettings.is_default == True).update({'is_default': False})

            # Handle storage path conversion - use media_save consistently
            if 'storage_path' in updates:
                updates['storage_path'] = current_app.media_save

            for key, value in updates.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)

            db.commit()

            return {
                'id': settings.id,
                'recording_mode': settings.recording_mode
            }

    @staticmethod
    def delete_settings(settings_id: int) -> Dict[str, Any]:
        """Soft delete camera settings"""
        with get_session() as db:
            settings = db.query(CameraSettings).filter(CameraSettings.id == settings_id).first()

            if not settings:
                raise ValueError(f"Camera settings with ID {settings_id} not found")

            db.commit()

            return {'id': settings_id, 'deleted': True}

    @staticmethod
    def get_default_settings() -> Optional[Dict[str, Any]]:
        """Get default camera settings"""
        with get_session() as db:
            settings = db.query(CameraSettings).filter(
                and_(CameraSettings.is_default == True, CameraSettings.is_active == True)
            ).first()

            if settings:
                return {
                    'id': settings.id,
                    'recording_mode': settings.recording_mode,
                    'interval_seconds': settings.interval_seconds,
                    'resolution': settings.resolution,
                    'storage_path': settings.storage_path,
                    'capture_on_button_click': settings.capture_on_button_click,
                    'capture_on_message_send': settings.capture_on_message_send,
                    'capture_on_question_start': settings.capture_on_question_start,
                    'is_default': settings.is_default
                }
            return None