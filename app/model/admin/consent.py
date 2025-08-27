# app/model/admin/consent.py
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Boolean
from ..base import BaseModel, StatusMixin


class ConsentSettings(BaseModel, StatusMixin):
    __tablename__ = 'consent_settings'
    
    setting_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    
    # Consent form content
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Additional settings
    require_signature: Mapped[bool] = mapped_column(Boolean, default=True)
    require_date: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_withdrawal: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Footer text
    footer_text: Mapped[Optional[str]] = mapped_column(Text)
    
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    
    def __repr__(self) -> str:
        return f"<ConsentSettings {self.setting_name}>"