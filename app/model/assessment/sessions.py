from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..base import BaseModel


class AssessmentSession(BaseModel):
    __tablename__ = 'assessment_sessions'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)

    # FK references to admin settings used for this session
    phq_settings_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('phq_settings.id'), nullable=True)
    llm_settings_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('llm_settings.id'), nullable=True)
    camera_settings_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('camera_settings.id'), nullable=True)

    # Session flow control (50:50 alternating PHQ/LLM first)
    is_first: Mapped[str] = mapped_column(String(10), nullable=False)  # 'phq' or 'llm'
    # CREATED → CONSENT → CAMERA_CHECK → PHQ_IN_PROGRESS/LLM_IN_PROGRESS → BOTH_IN_PROGRESS → COMPLETED/INCOMPLETE/ABANDONED
    status: Mapped[str] = mapped_column(String(20), default='CREATED')

    # Timestamps
    start_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    consent_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    phq_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    llm_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Session versioning and reset tracking  
    session_attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    session_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 or 2 (which session for this user)
    max_attempts: Mapped[int] = mapped_column(Integer, default=999, nullable=False)  # Unlimited resets
    reset_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reset_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reset_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Session metadata
    session_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    consent_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Session flow control
    assessment_order: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True)  # Store assessment order and generation status

    # Completion tracking
    completion_percentage: Mapped[int] = mapped_column(Integer, default=0)  # 0-100%
    failure_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    auto_deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    can_recover: Mapped[bool] = mapped_column(Boolean, default=True)  # Can this session be recovered/restarted

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
        return f'<AssessmentSession {self.id[:8]}: {self.is_first} first, status={self.status} for user {self.user_id}>'

    @property
    def completed_at(self) -> Optional[datetime]:
        """Alias for end_time for consistency"""
        return self.end_time

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
        self.completion_percentage = 100
        self.end_time = datetime.utcnow()

        if self.start_time and self.end_time:
            self.duration_seconds = int((self.end_time - self.start_time).total_seconds())

        self.updated_at = datetime.utcnow()

    def calculate_completion_percentage(self) -> int:
        """Calculate completion percentage based on completed steps"""
        if self.status == 'COMPLETED':
            return 100
        elif self.status == 'FAILED' or self.status == 'ABANDONED':
            return 0

        progress = 0
        # Consent completed: 25%
        if self.consent_completed_at:
            progress += 25

        # PHQ assessment: 35%
        if self.phq_completed_at:
            progress += 35

        # LLM assessment: 40%
        if self.llm_completed_at:
            progress += 40

        return min(progress, 100)

    def update_completion_percentage(self) -> None:
        """Update the completion percentage field"""
        self.completion_percentage = self.calculate_completion_percentage()

    def complete_phq(self) -> None:
        """Mark PHQ assessment as completed"""
        self.phq_completed_at = datetime.utcnow()
        if self.llm_completed_at:
            # Both assessments are done
            self.status = 'COMPLETED'
            self.complete_session()
        else:
            # PHQ done, now need LLM
            self.status = 'LLM_IN_PROGRESS'
        self.update_completion_percentage()
        self.updated_at = datetime.utcnow()

    def complete_llm(self) -> None:
        """Mark LLM assessment as completed"""
        self.llm_completed_at = datetime.utcnow()
        if self.phq_completed_at:
            # Both assessments are done
            self.status = 'COMPLETED'
            self.complete_session()
        else:
            # LLM done, now need PHQ
            self.status = 'PHQ_IN_PROGRESS'
        self.update_completion_percentage()
        self.updated_at = datetime.utcnow()

    def complete_consent(self, consent_data: Dict[str, Any]) -> None:
        """Mark consent as completed"""
        self.consent_data = consent_data
        self.consent_completed_at = datetime.utcnow()
        self.status = 'CAMERA_CHECK'
        self.update_completion_percentage()
        self.updated_at = datetime.utcnow()

    def complete_camera_check(self) -> None:
        """Mark camera check as completed and start first assessment"""
        # Add camera completion timestamp to metadata
        self.session_metadata = self.session_metadata or {}
        self.session_metadata['camera_completed_at'] = datetime.utcnow().isoformat()

        # Start first assessment based on is_first
        if self.is_first == 'phq':
            self.status = 'PHQ_IN_PROGRESS'
        else:
            self.status = 'LLM_IN_PROGRESS'
        self.update_completion_percentage()
        self.updated_at = datetime.utcnow()

    def mark_failed(self, reason: str = None) -> None:
        """Mark session as failed due to technical issues"""
        self.status = 'FAILED'
        self.is_active = False
        self.can_recover = False
        if reason:
            self.failure_reason = reason
        self.completion_percentage = 0
        self.updated_at = datetime.utcnow()

    def mark_incomplete(self, reason: str = None) -> None:
        """Mark session as incomplete but recoverable"""
        self.status = 'INCOMPLETE'
        self.is_active = False
        self.can_recover = True  # Allow recovery by default
        if reason:
            self.failure_reason = reason
        self.updated_at = datetime.utcnow()

    def mark_abandoned(self, reason: str = None) -> None:
        """Mark session as abandoned but recoverable"""
        self.status = 'ABANDONED'
        self.is_active = False
        self.can_recover = True  # Allow recovery
        if reason:
            self.failure_reason = reason
        self.updated_at = datetime.utcnow()

    def clear_assessment_data(self) -> None:
        """Clear all assessment responses to allow restart"""
        # This will be called by the service layer to clear PHQ/LLM data
        # Reset completion timestamps
        self.phq_completed_at = None
        self.llm_completed_at = None

        # Reset to camera check status (preserve consent)
        if self.consent_completed_at:
            self.status = 'CAMERA_CHECK'
        else:
            self.status = 'CONSENT'

        # Reset completion percentage
        self.completion_percentage = self.calculate_completion_percentage()
        self.is_active = True
        self.can_recover = True
        self.failure_reason = None
        self.updated_at = datetime.utcnow()

    def can_reset_to_new_attempt(self) -> bool:
        """Check if session can be reset to a new attempt - unlimited resets"""
        return self.status != 'COMPLETED'

    def reset_to_new_attempt(self, reason: str = None) -> bool:
        """Reset session to new attempt with version increment"""
        if not self.can_reset_to_new_attempt():
            return False
        
        # Increment attempt counter
        self.session_attempt += 1
        self.reset_count += 1
        self.last_reset_at = datetime.utcnow()
        self.reset_reason = reason
        
        # Clear all assessment data
        self.clear_assessment_data()
        
        # Clear chat history from session metadata
        if self.session_metadata and 'chat_history' in self.session_metadata:
            del self.session_metadata['chat_history']
        
        self.updated_at = datetime.utcnow()
        return True

    @property
    def session_display_name(self) -> str:
        """Get display name for session (Sesi 1, Sesi 2, etc)"""
        return f"Sesi {self.session_number}"

    @property 
    def has_incomplete_assessment_after_phq(self) -> bool:
        """Check if PHQ is completed but LLM is not (reset scenario)"""
        return (self.phq_completed_at is not None and 
                self.llm_completed_at is None and 
                self.status in ['PHQ_IN_PROGRESS', 'LLM_IN_PROGRESS'])

    def can_be_recovered(self) -> bool:
        """Check if this session can be recovered/restarted"""
        return (self.can_recover and
                self.status in ['INCOMPLETE', 'ABANDONED'] and
                not self.is_expired)

    @property
    def camera_completed(self) -> bool:
        """Check if camera check is completed"""
        return self.session_metadata and self.session_metadata.get('camera_completed_at') is not None

    @property
    def can_start_assessment(self) -> bool:
        """Check if session is ready to start assessments"""
        return (self.consent_completed_at is not None and
                self.camera_completed and
                self.status in ['PHQ_IN_PROGRESS', 'LLM_IN_PROGRESS', 'BOTH_IN_PROGRESS', 'CAMERA_CHECK', 'INCOMPLETE'])

    @property
    def next_assessment_type(self) -> Optional[str]:
        """Get the next assessment type that needs to be completed"""
        # If camera check just completed, start with the first assessment
        if self.status == 'CAMERA_CHECK' and self.camera_completed:
            return self.is_first

        # If session is already in progress, determine based on current status and completion
        if self.status == 'PHQ_IN_PROGRESS':
            if not self.phq_completed_at:
                return 'phq'  # Continue PHQ
            else:
                return 'llm'  # PHQ done, go to LLM
        elif self.status == 'LLM_IN_PROGRESS':
            if not self.llm_completed_at:
                return 'llm'  # Continue LLM
            else:
                return 'phq'  # LLM done, go to PHQ

        # Handle incomplete sessions - resume based on what's not completed
        if self.status == 'INCOMPLETE':
            if self.is_first == 'phq':
                if not self.phq_completed_at:
                    return 'phq'
                elif not self.llm_completed_at:
                    return 'llm'
            else:
                if not self.llm_completed_at:
                    return 'llm'
                elif not self.phq_completed_at:
                    return 'phq'

        # If we can't start assessments, return None
        if not self.can_start_assessment:
            return None

        # Determine next assessment based on completion status
        if self.is_first == 'phq':
            if not self.phq_completed_at:
                return 'phq'
            elif not self.llm_completed_at:
                return 'llm'
        else:
            if not self.llm_completed_at:
                return 'llm'
            elif not self.phq_completed_at:
                return 'phq'

        # Both completed
        return None


class PHQResponse(BaseModel):
    __tablename__ = 'phq_responses'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey('assessment_sessions.id'), nullable=False)
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
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey('assessment_sessions.id'), nullable=False)
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
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey('assessment_sessions.id'), nullable=False)
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
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey('assessment_sessions.id'), nullable=False)
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
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey('assessment_sessions.id'), nullable=False)

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
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey('assessment_sessions.id'), nullable=False)
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
