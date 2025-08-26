from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..base import BaseModel

class AssessmentSession(BaseModel):
    __tablename__ = 'assessment_sessions'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    session_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    
    status: Mapped[str] = mapped_column(String(20), default='STARTED')
    start_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    session_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    results: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    session_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="assessment_sessions")
    phq_responses = relationship("PHQResponse", back_populates="session", cascade="all, delete-orphan")
    open_question_responses = relationship("OpenQuestionResponse", back_populates="session", cascade="all, delete-orphan")
    camera_captures = relationship("CameraCapture", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<AssessmentSession {self.id}: {self.assessment_type} for user {self.user_id}>'
    
    @property
    def is_expired(self) -> bool:
        """Check if session is expired (24 hours)"""
        if not self.created_at:
            return True
        from datetime import timedelta
        return datetime.utcnow() - self.created_at > timedelta(hours=24)
    
    def complete_session(self, results: Optional[Dict[str, Any]] = None) -> None:
        """Mark session as completed"""
        self.is_completed = True
        self.status = 'COMPLETED'
        self.end_time = datetime.utcnow()
        
        if self.start_time and self.end_time:
            self.duration_seconds = int((self.end_time - self.start_time).total_seconds())
        
        if results:
            self.results = results
        
        self.updated_at = datetime.utcnow()

class PHQResponse(BaseModel):
    __tablename__ = 'phq_responses'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey('assessment_sessions.id'), nullable=False)
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_value: Mapped[int] = mapped_column(Integer, nullable=False)
    response_text: Mapped[str] = mapped_column(String(255), nullable=False)
    
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    session = relationship("AssessmentSession", back_populates="phq_responses")
    
    def __repr__(self):
        return f'<PHQResponse {self.id}: Q{self.question_number} = {self.response_value}>'

class OpenQuestionResponse(BaseModel):
    __tablename__ = 'open_question_responses'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey('assessment_sessions.id'), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    question_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_audio_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    transcription: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    audio_quality_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    sentiment_analysis: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    is_conversation_end: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    session = relationship("AssessmentSession", back_populates="open_question_responses")
    
    def __repr__(self):
        return f'<OpenQuestionResponse {self.id}: Seq {self.sequence_number}>'

class CameraCapture(BaseModel):
    __tablename__ = 'camera_captures'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey('assessment_sessions.id'), nullable=False)
    capture_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    capture_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    image_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    face_detection_results: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    emotion_analysis: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    image_dimensions: Mapped[Optional[Dict[str, int]]] = mapped_column(JSON, nullable=True)
    
    is_valid_capture: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    session = relationship("AssessmentSession", back_populates="camera_captures")
    
    def __repr__(self):
        return f'<CameraCapture {self.id}: Seq {self.capture_sequence} for session {self.session_id}>'
    
    @property
    def file_exists(self) -> bool:
        """Check if the image file exists"""
        import os
        return os.path.exists(self.image_path) if self.image_path else False

class SessionExport(BaseModel):
    __tablename__ = 'session_exports'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey('assessment_sessions.id'), nullable=False)
    export_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    export_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    requested_by_user: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    export_status: Mapped[str] = mapped_column(String(20), default='PENDING')
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    session = relationship("AssessmentSession")
    requested_by = relationship("User")
    
    def __repr__(self):
        return f'<SessionExport {self.id}: {self.export_type} for session {self.session_id}>'