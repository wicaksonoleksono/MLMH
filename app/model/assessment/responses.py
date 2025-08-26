# app/model/assessment/responses.py
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, DateTime, JSON, Float
from ..base import BaseModel


class BaseResponse(BaseModel):
    __tablename__ = 'responses'
    
    session_id: Mapped[int] = mapped_column(ForeignKey('assessment_sessions.id'), nullable=False)
    question_id: Mapped[str] = mapped_column(String(100), nullable=False)  # Flexible question identifier
    question_text: Mapped[Optional[str]] = mapped_column(Text)
    response_type: Mapped[str] = mapped_column(String(20), nullable=False)  # PHQ, OPEN, CAMERA
    
    # Polymorphic identity
    __mapper_args__ = {
        'polymorphic_identity': 'base',
        'polymorphic_on': response_type
    }
    
    # Relationships
    session: Mapped["AssessmentSession"] = relationship("AssessmentSession", back_populates="responses")
    
    def __repr__(self) -> str:
        return f"<BaseResponse {self.question_id} ({self.response_type})>"


class PHQResponse(BaseResponse):
    __tablename__ = 'phq_responses'
    
    id: Mapped[int] = mapped_column(ForeignKey('responses.id'), primary_key=True)
    
    # PHQ-specific fields
    score_value: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-3 for PHQ questions
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)  # PHQ question sequence
    
    # Optional additional data
    time_taken_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    response_metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    
    __mapper_args__ = {
        'polymorphic_identity': 'PHQ'
    }
    
    def __repr__(self) -> str:
        return f"<PHQResponse Q{self.question_number}: {self.score_value}>"
    
    @property
    def score_description(self) -> str:
        """Convert numeric score to description"""
        descriptions = {
            0: "Not at all",
            1: "Several days", 
            2: "More than half the days",
            3: "Nearly every day"
        }
        return descriptions.get(self.score_value, "Unknown")


class OpenQuestionResponse(BaseResponse):
    __tablename__ = 'open_responses'
    
    id: Mapped[int] = mapped_column(ForeignKey('responses.id'), primary_key=True)
    
    # Open question specific fields
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Analysis fields
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float)
    keywords: Mapped[Optional[dict]] = mapped_column(JSON)  # Extracted keywords and frequency
    
    # Processing metadata
    processing_status: Mapped[str] = mapped_column(String(20), default='PENDING')  # PENDING, PROCESSED, ERROR
    processed_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
    
    # Conversation detection
    conversation_ended: Mapped[bool] = mapped_column(Boolean, default=False)
    conversation_metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    
    __mapper_args__ = {
        'polymorphic_identity': 'OPEN'
    }
    
    def __repr__(self) -> str:
        preview = self.response_text[:50] + "..." if len(self.response_text) > 50 else self.response_text
        return f"<OpenQuestionResponse: {preview}>"
    
    @property
    def is_processed(self) -> bool:
        return self.processing_status == 'PROCESSED'


class CameraResponse(BaseResponse):
    __tablename__ = 'camera_responses'
    
    id: Mapped[int] = mapped_column(ForeignKey('responses.id'), primary_key=True)
    
    # Camera/Media specific fields
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)  # IMAGE, VIDEO, AUDIO
    file_path: Mapped[Optional[str]] = mapped_column(String(500))  # Physical file path
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    file_format: Mapped[Optional[str]] = mapped_column(String(10))  # jpg, png, mp4, etc.
    
    # Camera settings JSON (from the assessment configuration)
    camera_settings: Mapped[Optional[dict]] = mapped_column(JSON)
    
    # Media analysis
    analysis_result: Mapped[Optional[dict]] = mapped_column(JSON)  # AI/ML analysis results
    analysis_status: Mapped[str] = mapped_column(String(20), default='PENDING')  # PENDING, COMPLETED, FAILED
    
    # Upload/processing metadata
    upload_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    processing_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    __mapper_args__ = {
        'polymorphic_identity': 'CAMERA'
    }
    
    def __repr__(self) -> str:
        return f"<CameraResponse {self.media_type}: {self.file_path or 'No file'}>"
    
    @property
    def is_uploaded(self) -> bool:
        return self.upload_completed and self.file_path is not None
    
    @property
    def is_analyzed(self) -> bool:
        return self.analysis_status == 'COMPLETED'
    
    @property
    def file_size_mb(self) -> Optional[float]:
        if self.file_size_bytes:
            return round(self.file_size_bytes / (1024 * 1024), 2)
        return None