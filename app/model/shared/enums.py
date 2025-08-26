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
