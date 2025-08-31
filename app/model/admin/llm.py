# app/model/admin/llm.py
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, JSON, Boolean
from ..base import BaseModel, StatusMixin
from ...services.shared.encryptionService import EncryptionService


class LLMSettings(BaseModel, StatusMixin):
    __tablename__ = 'llm_settings'
    instructions: Mapped[Optional[str]] = mapped_column(Text)
    openai_api_key: Mapped[str] = mapped_column(Text, nullable=False)  # Stores encrypted API key
    chat_model: Mapped[str] = mapped_column(String(50), default="gpt-4o", nullable=False)
    analysis_model: Mapped[str] = mapped_column(String(50), default="gpt-4o-mini", nullable=False)
    depression_aspects: Mapped[dict] = mapped_column(JSON, nullable=False)
    analysis_scale: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Shared scale for all aspects
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    
    def set_api_key(self, plain_api_key: str) -> None:
        """Encrypt and store API key"""
        if plain_api_key and plain_api_key.strip():
            self.openai_api_key = EncryptionService.encrypt_api_key(plain_api_key)
        else:
            self.openai_api_key = ""
    
    def get_api_key(self) -> str:
        """Decrypt and return API key for use"""
        if not self.openai_api_key:
            return ""
        # If it's already a plain text key (migration scenario), return as-is
        if EncryptionService.is_encrypted(self.openai_api_key):
            return EncryptionService.decrypt_api_key(self.openai_api_key)
        else:
            # Legacy plain text key - encrypt it on next save
            return self.openai_api_key
    
    def get_masked_api_key(self) -> str:
        """Get masked version for UI display"""
        if not self.openai_api_key:
            return ""
        try:
            # Get the plain text version first
            plain_key = self.get_api_key()
            return EncryptionService.mask_api_key(plain_key)
        except:
            # If decrypion fails, return a generic mask
            return "••••••••••••[encrypted]"
    def __repr__(self) -> str:
        masked_key = self.get_masked_api_key()[:12] + "..." if self.openai_api_key else "None"
        return f"<LLMSettings {self.id} (Key:{masked_key}, Chat:{self.chat_model}, Analysis:{self.analysis_model})>"