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
            # At least one event trigger must be enabled
            if not any([capture_on_button_click, capture_on_message_send, capture_on_question_start]):
                raise ValueError("EVENT_DRIVEN mode requires at least one capture trigger to be enabled")
        
        from flask import current_app
        with get_session() as db:
            # Look for existing settings (assume only one set of settings for now)
            existing = db.query(CameraSettings).filter(CameraSettings.is_active == True).first()
            
            if is_default:
                # Remove default from other settings
                db.query(CameraSettings).filter(CameraSettings.is_default == True).update({'is_default': False})
            
            if existing:
                # Update existing settings
                existing.recording_mode = recording_mode
                existing.interval_seconds = interval_seconds
                existing.resolution = resolution
                existing.storage_path = current_app.media_save
                existing.capture_on_button_click = capture_on_button_click
                existing.capture_on_message_send = capture_on_message_send
                existing.capture_on_question_start = capture_on_question_start
                existing.is_default = is_default
                
                # Set is_active based on field completeness
                if recording_mode == 'INTERVAL':
                    all_fields_valid = (
                        existing.recording_mode and existing.recording_mode.strip() != '' and
                        existing.resolution and existing.resolution.strip() != '' and
                        existing.storage_path and existing.storage_path.strip() != '' and
                        existing.interval_seconds is not None and existing.interval_seconds >= 1
                    )
                else:  # EVENT_DRIVEN
                    all_fields_valid = (
                        existing.recording_mode and existing.recording_mode.strip() != '' and
                        existing.resolution and existing.resolution.strip() != '' and
                        existing.storage_path and existing.storage_path.strip() != '' and
                        any([existing.capture_on_button_click, existing.capture_on_message_send, existing.capture_on_question_start])
                    )
                # Ensure is_active is never None
                existing.is_active = bool(all_fields_valid)
                
                settings = existing
                
            else:
                # Create new settings
                settings = CameraSettings(
                    recording_mode=recording_mode,
                    interval_seconds=interval_seconds,
                    resolution=resolution,
                    storage_path=current_app.media_save,
                    capture_on_button_click=capture_on_button_click,
                    capture_on_message_send=capture_on_message_send,
                    capture_on_question_start=capture_on_question_start,
                    is_default=is_default
                )
                
                # Set is_active based on field completeness
                if recording_mode == 'INTERVAL':
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
                # Ensure is_active is never None
                settings.is_active = bool(all_fields_valid)
                
                db.add(settings)
            
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
        # 🚨 DEBUG: Log what frontend is sending
        print(f"🔍 DEBUG update_settings received: {updates}")
        for key, value in updates.items():
            print(f"  {key}: {type(value).__name__} = {value}")
        
        # 🚨 DETECT FIELD MAPPING BUG: is_active should never be None or dict
        if 'is_active' in updates:
            if updates['is_active'] is None:
                print(f"🚨 BUG DETECTED: is_active is None! Frontend is sending wrong field mapping.")
                print(f"   is_active value: {updates['is_active']}")
                del updates['is_active']
                print(f"   Removed is_active from updates to prevent crash.")
            elif isinstance(updates['is_active'], dict):
                print(f"🚨 BUG DETECTED: is_active is a dict! Frontend is sending wrong field mapping.")
                print(f"   is_active value: {updates['is_active']}")
                del updates['is_active']
                print(f"   Removed is_active from updates to prevent crash.")
        
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
                if hasattr(settings, key) and key != 'is_active':  # Skip is_active field, it's auto-calculated
                    setattr(settings, key, value)
            
            # Recalculate is_active based on field completeness
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