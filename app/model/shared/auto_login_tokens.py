from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import String, ForeignKey, DateTime, Boolean, or_
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..base import BaseModel


class AutoLoginToken(BaseModel):
    __tablename__ = 'auto_login_tokens'
    
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete='CASCADE'), nullable=False)
    token_jti: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)  # JWT ID for tracking
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)  # auto_login_session2, auto_login_password_reset, etc.
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    
    @classmethod
    def create_token_record(cls, user_id: int, token_jti: str, purpose: str, expires_at: datetime) -> "AutoLoginToken":
        """Create a new token tracking record."""
        return cls(
            user_id=user_id,
            token_jti=token_jti,
            purpose=purpose,
            used=False,
            expires_at=expires_at
        )
    
    def mark_as_used(self) -> None:
        """Mark token as used."""
        self.used = True
        self.used_at = datetime.utcnow()
    
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if token is valid (not used and not expired)."""
        return not self.used and not self.is_expired()
    
    @classmethod
    def find_valid_token(cls, token_jti: str) -> Optional["AutoLoginToken"]:
        """Find a valid token by JTI."""
        from ...db import get_session
        
        with get_session() as db:
            token = db.query(cls).filter(
                cls.token_jti == token_jti,
                cls.used == False,
                cls.expires_at > datetime.utcnow()
            ).first()
            
            return token
    
    @classmethod
    def cleanup_expired_tokens(cls) -> int:
        """Clean up expired and used tokens."""
        from ...db import get_session
        
        with get_session() as db:
            # Delete tokens that are expired or older than 7 days
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            
            expired_tokens = db.query(cls).filter(
                or_(
                    cls.expires_at < datetime.utcnow(),
                    cls.created_at < cutoff_date
                )
            )
            
            count = expired_tokens.count()
            expired_tokens.delete()
            db.commit()
            
            return count
    
    def __repr__(self) -> str:
        return f"<AutoLoginToken user_id={self.user_id} purpose={self.purpose} used={self.used}>"