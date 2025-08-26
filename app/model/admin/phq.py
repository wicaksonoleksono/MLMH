# app/model/admin/phq.py
from __future__ import annotations

from typing import Optional, List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, JSON, ForeignKey, Boolean
from ..base import BaseModel, StatusMixin


class PHQCategory(BaseModel, StatusMixin):
    __tablename__ = 'phq_categories'
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # ANHEDONIA, DEPRESSED_MOOD, etc
    description_en: Mapped[Optional[str]] = mapped_column(Text)
    description_id: Mapped[Optional[str]] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    questions: Mapped[List["PHQQuestion"]] = relationship("PHQQuestion", back_populates="category")
    
    def __repr__(self) -> str:
        return f"<PHQCategory {self.name_id}>"


class PHQQuestion(BaseModel, StatusMixin):
    __tablename__ = 'phq_questions'
    
    category_id: Mapped[int] = mapped_column(ForeignKey('phq_categories.id'), nullable=False)
    question_text_en: Mapped[str] = mapped_column(Text, nullable=False)
    question_text_id: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    category: Mapped["PHQCategory"] = relationship("PHQCategory", back_populates="questions")
    
    def __repr__(self) -> str:
        return f"<PHQQuestion {self.id} - {self.category.name_id}>"


class PHQScale(BaseModel, StatusMixin):
    __tablename__ = 'phq_scales'
    
    scale_name: Mapped[str] = mapped_column(String(100), nullable=False)
    min_value: Mapped[int] = mapped_column(Integer, nullable=False)
    max_value: Mapped[int] = mapped_column(Integer, nullable=False)
    scale_labels: Mapped[dict] = mapped_column(JSON, nullable=False)  # {0: "Tidak sama sekali", 1: "Beberapa hari", ...}
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    
    def __repr__(self) -> str:
        return f"<PHQScale {self.scale_name} ({self.min_value}-{self.max_value})>"


class PHQSettings(BaseModel, StatusMixin):
    __tablename__ = 'phq_settings'
    
    setting_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    questions_per_category: Mapped[int] = mapped_column(Integer, default=1)
    scale_id: Mapped[int] = mapped_column(ForeignKey('phq_scales.id'), nullable=False)
    randomize_questions: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    scale: Mapped["PHQScale"] = relationship("PHQScale")
    
    def __repr__(self) -> str:
        return f"<PHQSettings {self.setting_name}>"