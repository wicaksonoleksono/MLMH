from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..base import BaseModel


class AssessmentSession(BaseModel):
    __tablename__ = 'assessment_sessions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    session_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # FK references to admin settings used for this session
    phq_settings_id: Mapped[int] = mapped_column(Integer, ForeignKey('phq_settings.id'), nullable=False)
    llm_settings_id: Mapped[int] = mapped_column(Integer, ForeignKey('llm_settings.id'), nullable=False)
    camera_settings_id: Mapped[int] = mapped_column(Integer, ForeignKey('camera_settings.id'), nullable=False)

    # Session flow control (50:50 alternating PHQ/LLM first)
    is_first: Mapped[str] = mapped_column(String(10), nullable=False)  # 'phq' or 'llm'
    status: Mapped[str] = mapped_column(String(20), default='STARTED')  # STARTED → CONSENT → PHQ → LLM → COMPLETED

    # Timestamps
    start_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    consent_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    phq_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    llm_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Session metadata
    session_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    consent_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")
    phq_settings = relationship("PHQSettings")
    llm_settings = relationship("LLMSettings")
    camera_settings = relationship("CameraSettings")

    # Response data relationships
    phq_responses = relationship("PHQResponse", back_populates="session", cascade="all, delete-orphan")
    llm_conversations = relationship("LLMConversationTurn", back_populates="session", cascade="all, delete-orphan")
    open_question_responses = relationship(
        "OpenQuestionResponse", back_populates="session", cascade="all, delete-orphan")
    llm_analysis = relationship("LLMAnalysisResult", back_populates="session", cascade="all, delete-orphan")
    camera_captures = relationship("CameraCapture", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f'<AssessmentSession {self.id}: {self.is_first} first, status={self.status} for user {self.user_id}>'

    @property
    def is_expired(self) -> bool:
        """Check if session is expired (24 hours)"""
        if not self.created_at:
            return True
        from datetime import timedelta
        return datetime.utcnow() - self.created_at > timedelta(hours=24)

    def complete_session(self) -> None:
        """Mark session as completed"""
        self.is_completed = True
        self.status = 'COMPLETED'
        self.end_time = datetime.utcnow()

        if self.start_time and self.end_time:
            self.duration_seconds = int((self.end_time - self.start_time).total_seconds())

        self.updated_at = datetime.utcnow()

    def complete_phq(self) -> None:
        """Mark PHQ assessment as completed"""
        self.phq_completed_at = datetime.utcnow()
        if self.status == 'STARTED' or self.status == 'CONSENT':
            self.status = 'PHQ_COMPLETED'
        elif self.status == 'LLM_COMPLETED':
            self.status = 'COMPLETED'
            self.complete_session()
        self.updated_at = datetime.utcnow()

    def complete_llm(self) -> None:
        """Mark LLM assessment as completed"""
        self.llm_completed_at = datetime.utcnow()
        if self.status == 'STARTED' or self.status == 'CONSENT':
            self.status = 'LLM_COMPLETED'
        elif self.status == 'PHQ_COMPLETED':
            self.status = 'COMPLETED'
            self.complete_session()
        self.updated_at = datetime.utcnow()

    def complete_consent(self, consent_data: Dict[str, Any]) -> None:
        """Mark consent as completed"""
        self.consent_data = consent_data
        self.consent_completed_at = datetime.utcnow()
        self.status = 'CONSENT'
        self.updated_at = datetime.utcnow()


class PHQResponse(BaseModel):
    __tablename__ = 'phq_responses'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey('assessment_sessions.id'), nullable=False)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey('phq_questions.id'), nullable=False)

    # Question metadata (snapshot at response time)
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    category_name: Mapped[str] = mapped_column(String(50), nullable=False)  # ANHEDONIA, DEPRESSED_MOOD, etc.

    # Response data
    response_value: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-3 scale value
    response_text: Mapped[str] = mapped_column(String(255), nullable=False)  # Human-readable answer
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("AssessmentSession", back_populates="phq_responses")
    question = relationship("PHQQuestion")

    def __repr__(self):
        return f'<PHQResponse {self.id}: Q{self.question_number} = {self.response_value}>'


class LLMConversationTurn(BaseModel):
    __tablename__ = 'llm_conversation_turns'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey('assessment_sessions.id'), nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, 3... conversation flow

    # Conversation data
    ai_message: Mapped[str] = mapped_column(Text, nullable=False)  # Anisa's question/response
    user_message: Mapped[str] = mapped_column(Text, nullable=False)  # User's answer

    # Detection flags
    has_end_conversation: Mapped[bool] = mapped_column(Boolean, default=False)  # </end_conversation> detected

    # Conversation metadata
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user_message_length: Mapped[int] = mapped_column(Integer, nullable=False)  # For analysis
    ai_model_used: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Track which model was used

    # Optional audio/transcription support
    response_audio_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    transcription: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audio_quality_score: Mapped[Optional[float]] = mapped_column(nullable=True)

    session = relationship("AssessmentSession", back_populates="llm_conversations")

    def __repr__(self):
        return f'<LLMConversationTurn {self.id}: Turn {self.turn_number} (Session {self.session_id})>'


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


class LLMAnalysisResult(BaseModel):
    __tablename__ = 'llm_analysis_results'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey('assessment_sessions.id'), nullable=False)

    # Analysis metadata
    analysis_model_used: Mapped[str] = mapped_column(String(50), nullable=False)  # gpt-4o-mini, etc.
    conversation_turns_analyzed: Mapped[int] = mapped_column(Integer, nullable=False)  # How many turns were analyzed

    # Raw analysis results (JSON with standardized aspect keys)
    raw_analysis_result: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Processed individual aspect scores
    # {"anhedonia": {"score": 2, "explanation": "..."}, ...}
    aspect_scores: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Overall analysis summary
    total_aspects_detected: Mapped[int] = mapped_column(Integer, nullable=False)
    average_severity_score: Mapped[float] = mapped_column(nullable=False)  # 0-3 average
    analysis_confidence: Mapped[Optional[float]] = mapped_column(nullable=True)  # AI confidence in analysis

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session = relationship("AssessmentSession")

    def __repr__(self):
        return f'<LLMAnalysisResult {self.id}: {self.total_aspects_detected} aspects for session {self.session_id}>'


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
