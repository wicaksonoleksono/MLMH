"""
Enum Tables - Replace hardcoded enums with proper database tables
All these were previously hardcoded strings or Python enums
"""
from typing import List, Optional

from sqlalchemy import String, Integer, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import BaseModel, NamedModel, StatusMixin


class AssessmentStatus(NamedModel, StatusMixin):
    """Status of an assessment (in_progress, completed, abandoned, etc.)"""
    __tablename__ = 'assessment_status'


class UserType(NamedModel, StatusMixin):
    """User types (admin,user)"""
    __tablename__ = 'user_type'
    permissions: Mapped[Optional[str]] = mapped_column(Text)
    users: Mapped[List["User"]] = relationship(back_populates="user_type")


class MediaType(NamedModel):
    """Media types (image, video) with their allowed extensions"""
    __tablename__ = 'media_type'
    extensions: Mapped[Optional[str]] = mapped_column(String(100))  # 'jpg,png,webp'
    mime_types: Mapped[Optional[str]] = mapped_column(String(200))  # 'image/jpeg,image/png'
    max_file_size_mb: Mapped[Optional[int]] = mapped_column(Integer, default=50)



class AssessmentType(NamedModel):
    """Types of assessments (PHQ, open_questions)"""
    __tablename__ = 'assessment_type'

    # Configuration for this assessment type
    instructions: Mapped[Optional[str]] = mapped_column(Text)
    default_order: Mapped[Optional[int]] = mapped_column(Integer)



class PHQCategory(BaseModel):
    """PHQ categories"""
    __tablename__ = 'PHQ_category'
    number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    default_question: Mapped[Optional[str]] = mapped_column(Text)
    name_en: Mapped[Optional[str]] = mapped_column(String(100))
    description_en: Mapped[Optional[str]] = mapped_column(Text)
    default_question_en: Mapped[Optional[str]] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<PHQCategory {self.number}: {self.name}>"


class ScaleLabel(BaseModel):
    """Dynamic scale labels - formerly hardcoded SCALE_LABEL_* values"""
    __tablename__ = 'scale_label'
    scale_value: Mapped[int] = mapped_column(Integer, nullable=False)
    label_text: Mapped[str] = mapped_column(String(100), nullable=False)
    language: Mapped[str] = mapped_column(String(5), default='id')  # 'id', 'en'
    context: Mapped[Optional[str]] = mapped_column(String(50))  # 'PHQ', 'general'

    def __repr__(self) -> str:
        return f"<ScaleLabel {self.scale_value}: {self.label_text} ({self.language})>"


class SettingType(NamedModel):
    """Types of settings (recording, PHQ, chat, etc.)"""
    __tablename__ = 'setting_type'
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'string', 'int', 'bool', 'float', 'json'
    default_value: Mapped[Optional[str]] = mapped_column(Text)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    choices: Mapped[Optional[str]] = mapped_column(Text)  # JSON array of choices

    def __repr__(self) -> str:
        return f"<SettingType {self.name} ({self.data_type})>"
