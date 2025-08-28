# app/services/admin/cameraService.py
import os
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
                'setting_name': setting.setting_name,
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
    def create_settings(recording_mode: str, storage_path: str = "recordings",
                       interval_seconds: Optional[int] = None, resolution: str = "1280x720",
                       capture_on_button_click: bool = True, capture_on_message_send: bool = False,
                       capture_on_question_start: bool = False, is_default: bool = False) -> Dict[str, Any]:
        """Create or update camera settings"""
        with get_session() as db:
            # Convert relative storage path to absolute using app root
            if not os.path.isabs(storage_path):
                absolute_storage_path = os.path.join(current_app.root_path, storage_path)
            else:
                absolute_storage_path = storage_path

            # Auto-generate setting name based on mode
            setting_name = f"Camera {recording_mode.title()} Settings"
            
            # Look for existing settings (assume only one set of settings for now)
            existing = db.query(CameraSettings).filter(CameraSettings.is_active == True).first()
            
            if is_default:
                # Remove default from other settings
                db.query(CameraSettings).filter(CameraSettings.is_default == True).update({'is_default': False})
            
            if existing:
                # Update existing settings
                existing.setting_name = setting_name
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
                    setting_name=setting_name,
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

            # Auto-set is_active based on field completeness
            all_fields_valid = (
                settings.setting_name and settings.setting_name.strip() != '' and
                settings.recording_mode and settings.recording_mode.strip() != '' and
                settings.resolution and settings.resolution.strip() != '' and
                settings.storage_path and settings.storage_path.strip() != '' and
                settings.interval_seconds is not None  # 0 is valid for interval_seconds
            )
            settings.is_active = all_fields_valid
            
            db.commit()

            return {
                'id': settings.id,
                'setting_name': settings.setting_name,
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

            # Handle storage path conversion
            if 'storage_path' in updates:
                storage_path = updates['storage_path']
                if not os.path.isabs(storage_path):
                    updates['storage_path'] = os.path.join(current_app.root_path, storage_path)

            for key, value in updates.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)

            db.commit()

            return {
                'id': settings.id,
                'setting_name': settings.setting_name,
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
                    'setting_name': settings.setting_name,
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