# app/model/admin/camera.py
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean
from ..base import BaseModel, StatusMixin


class CameraSettings(BaseModel, StatusMixin):
    __tablename__ = 'camera_settings'
    
    setting_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    recording_mode: Mapped[str] = mapped_column(String(20), nullable=False)  # INTERVAL, EVENT_DRIVEN
    interval_seconds: Mapped[Optional[int]] = mapped_column(Integer)  # Required for INTERVAL mode
    resolution: Mapped[str] = mapped_column(String(20), default="1280x720")  # Camera resolution
    storage_path: Mapped[str] = mapped_column(String(255), nullable=False)  # Absolute path from app.root
    # Event-driven settings
    capture_on_button_click: Mapped[bool] = mapped_column(Boolean, default=True)
    capture_on_message_send: Mapped[bool] = mapped_column(Boolean, default=False)
    capture_on_question_start: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    
    def __repr__(self) -> str:
        return f"<CameraSettings {self.setting_name} ({self.recording_mode})>"