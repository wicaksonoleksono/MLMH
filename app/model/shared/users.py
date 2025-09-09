from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash as gpw, check_password_hash as cpw
from sqlalchemy import String, Boolean, ForeignKey, Text, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..base import BaseModel, StatusMixin

if TYPE_CHECKING:
    from .enums import UserType


class User(BaseModel, UserMixin, StatusMixin):
    __tablename__ = 'users'
    
    uname: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    
    # Extended profile fields (only for regular users)
    age: Mapped[Optional[int]] = mapped_column(Integer)
    gender: Mapped[Optional[str]] = mapped_column(String(20))
    educational_level: Mapped[Optional[str]] = mapped_column(String(100))
    cultural_background: Mapped[Optional[str]] = mapped_column(String(100))
    medical_conditions: Mapped[Optional[str]] = mapped_column(Text)
    medications: Mapped[Optional[str]] = mapped_column(Text)
    emergency_contact: Mapped[Optional[str]] = mapped_column(String(200))
    
    # Email OTP verification fields
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_otp_code: Mapped[Optional[str]] = mapped_column(String(6))
    email_otp_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Foreign key to UserType
    user_type_id: Mapped[int] = mapped_column(ForeignKey("user_type.id"), nullable=False)
    
    # Relationships
    user_type: Mapped["UserType"] = relationship("UserType", back_populates="users")
    
    def set_password(self, password: str) -> None:
        """Set password hash."""
        self.password_hash = gpw(password)
    
    def check_password(self, password: str) -> bool:
        """Check if provided password matches hash."""
        return cpw(self.password_hash, password)
    
    def is_admin(self) -> bool:
        """Check if user is admin type."""
        return self.user_type.name.lower() == 'admin'
    
    def is_user(self) -> bool:
        """Check if user is regular user type."""
        return self.user_type.name.lower() == 'user'
    
    @classmethod
    def create_user(cls, uname: str, password: str, user_type_id: int, 
                   email: Optional[str] = None, phone: Optional[str] = None,
                   age: Optional[int] = None, gender: Optional[str] = None,
                   educational_level: Optional[str] = None, cultural_background: Optional[str] = None,
                   medical_conditions: Optional[str] = None, medications: Optional[str] = None,
                   emergency_contact: Optional[str] = None) -> "User":
        """Create a new user with basic and extended profile information."""
        user = cls(
            uname=uname,
            user_type_id=user_type_id,
            email=email,
            phone=phone,
            age=age,
            gender=gender,
            educational_level=educational_level,
            cultural_background=cultural_background,
            medical_conditions=medical_conditions,
            medications=medications,
            emergency_contact=emergency_contact
        )
        user.set_password(password)
        return user
    
    def __repr__(self) -> str:
        return f"<User {self.uname}>"
