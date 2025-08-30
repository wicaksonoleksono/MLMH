# app/model/admin/camera.py
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean
from ..base import BaseModel, StatusMixin

class CameraSettings(BaseModel, StatusMixin):
    __tablename__ = 'camera_settings'
    
    recording_mode: Mapped[str] = mapped_column(String(20), nullable=False)  # INTERVAL, EVENT_DRIVEN
    interval_seconds: Mapped[Optional[int]] = mapped_column(Integer)  # Required for INTERVAL mode
    resolution: Mapped[str] = mapped_column(String(20), default="1280x720")  # Camera resolution
    storage_path: Mapped[str] = mapped_column(String(255), nullable=False)  # Absolute path from app.root
    # Event-driven settings
    capture_on_button_click: Mapped[bool] = mapped_column(Boolean, default=True)
    capture_on_message_send: Mapped[bool] = mapped_column(Boolean, default=False)
    capture_on_question_start: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    def validate_mutually_exclusive_modes(self) -> None:
        """Validate that camera settings are mutually exclusive and consistent"""
        if self.recording_mode == 'INTERVAL':
            if self.interval_seconds is None or self.interval_seconds < 1:
                raise ValueError("INTERVAL mode requires interval_seconds >= 1")
            # Ensure event triggers are disabled for INTERVAL mode
            if self.capture_on_button_click or self.capture_on_message_send or self.capture_on_question_start:
                raise ValueError("INTERVAL mode cannot have event triggers enabled - mutually exclusive!")
        elif self.recording_mode == 'EVENT_DRIVEN':
            if self.interval_seconds is not None:
                raise ValueError("EVENT_DRIVEN mode cannot have interval_seconds - mutually exclusive!")
            if not any([self.capture_on_button_click, self.capture_on_message_send, self.capture_on_question_start]):
                raise ValueError("EVENT_DRIVEN mode requires at least one event trigger enabled")
        
        else:
            raise ValueError(f"Invalid recording_mode: {self.recording_mode}. Must be 'INTERVAL' or 'EVENT_DRIVEN'")

    def __repr__(self) -> str:
        return f"<CameraSettings {self.id} ({self.recording_mode})>"