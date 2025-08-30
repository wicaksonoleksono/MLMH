# app/model/admin/llm.py
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, JSON, Boolean
from ..base import BaseModel, StatusMixin


class LLMSettings(BaseModel, StatusMixin):
    __tablename__ = 'llm_settings'
    instructions: Mapped[Optional[str]] = mapped_column(Text)
    openai_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    chat_model: Mapped[str] = mapped_column(String(50), default="gpt-4o", nullable=False)
    analysis_model: Mapped[str] = mapped_column(String(50), default="gpt-4o-mini", nullable=False)
    depression_aspects: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    def __repr__(self) -> str:
        return f"<LLMSettings {self.id} (Chat:{self.chat_model}, Analysis:{self.analysis_model})>"