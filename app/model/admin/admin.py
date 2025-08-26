# app/model/admin/admin.py
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Boolean, JSON, Integer
from ..base import BaseModel, StatusMixin


class SystemSetting(BaseModel, StatusMixin):
    __tablename__ = 'system_settings'
    
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[Optional[str]] = mapped_column(Text)
    data_type: Mapped[str] = mapped_column(String(20), default='string')  # string, integer, boolean, json
    category: Mapped[str] = mapped_column(String(50), default='general')
    description: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Admin control
    is_editable: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_restart: Mapped[bool] = mapped_column(Boolean, default=False)
    
    def __repr__(self) -> str:
        return f"<SystemSetting {self.key}={self.value}>"
    
    @property
    def parsed_value(self):
        """Parse value based on data_type"""
        if not self.value:
            return None
            
        if self.data_type == 'integer':
            try:
                return int(self.value)
            except ValueError:
                return 0
        elif self.data_type == 'boolean':
            return self.value.lower() in ('true', '1', 'yes', 'on')
        elif self.data_type == 'json':
            try:
                import json
                return json.loads(self.value)
            except (ValueError, TypeError):
                return {}
        else:
            return self.value


class AssessmentConfig(BaseModel, StatusMixin):
    __tablename__ = 'assessment_configs'
    
    config_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(50), nullable=False)  # PHQ, OPEN, CAMERA
    config_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    version: Mapped[str] = mapped_column(String(20), default='1.0')
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Admin metadata
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_admin: Mapped[Optional[str]] = mapped_column(String(50))
    
    def __repr__(self) -> str:
        return f"<AssessmentConfig {self.config_name} ({self.assessment_type})>"


class MediaSetting(BaseModel, StatusMixin):
    __tablename__ = 'media_settings'
    
    setting_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)  # IMAGE, VIDEO, AUDIO
    
    # File size and format constraints
    max_file_size_mb: Mapped[int] = mapped_column(Integer, default=10)
    allowed_formats: Mapped[list] = mapped_column(JSON, default=['jpg', 'png', 'mp4'])
    
    # Camera/recording settings
    camera_settings: Mapped[Optional[dict]] = mapped_column(JSON)
    
    # Processing settings
    auto_process: Mapped[bool] = mapped_column(Boolean, default=True)
    processing_timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)
    
    # Storage settings
    storage_path: Mapped[Optional[str]] = mapped_column(String(500))
    retention_days: Mapped[int] = mapped_column(Integer, default=90)
    
    def __repr__(self) -> str:
        return f"<MediaSetting {self.setting_name} ({self.media_type})>"


class AdminLog(BaseModel):
    __tablename__ = 'admin_logs'
    
    admin_user: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50))  # USER, SETTING, ASSESSMENT, etc.
    target_id: Mapped[Optional[str]] = mapped_column(String(100))
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    
    def __repr__(self) -> str:
        return f"<AdminLog {self.admin_user}: {self.action}>"


class QuestionPool(BaseModel, StatusMixin):
    __tablename__ = 'question_pools'
    
    pool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    question_type: Mapped[str] = mapped_column(String(50), nullable=False)  # PHQ, OPEN, CAMERA
    language: Mapped[str] = mapped_column(String(10), default='en')
    
    # Question content
    questions: Mapped[list] = mapped_column(JSON, nullable=False)  # List of question objects
    pool_metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    
    # Pool configuration
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    randomize_order: Mapped[bool] = mapped_column(Boolean, default=False)
    
    def __repr__(self) -> str:
        return f"<QuestionPool {self.pool_name} ({self.question_type})>"
    
    @property
    def question_count(self) -> int:
        return len(self.questions) if self.questions else 0