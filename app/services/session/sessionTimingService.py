# app/services/session/sessionTimingService.py
from datetime import datetime
from typing import Optional
from ...db import get_session
from ...model.assessment.sessions import AssessmentSession


class SessionTimingService:
    """Service for calculating unified session timing across all assessments"""
    
    @staticmethod
    def get_session_time(session_id: str, current_time: Optional[datetime] = None) -> int:
        """
        Get session time in seconds from session start time
        Returns 0-based seconds elapsed since session started
        """
        if current_time is None:
            current_time = datetime.utcnow()
            
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session or not session.start_time:
                return 0
            
            # Calculate seconds elapsed since session start
            time_delta = current_time - session.start_time
            session_time = int(time_delta.total_seconds())
            
            # Ensure non-negative time
            return max(0, session_time)
    
    @staticmethod
    def get_phq_assessment_time(session_id: str, current_time: Optional[datetime] = None) -> int:
        """
        Get PHQ assessment-relative time in seconds
        Returns seconds elapsed since PHQ assessment started
        """
        if current_time is None:
            current_time = datetime.utcnow()
            
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session or not session.phq_start_time:
                return 0
            
            # Calculate seconds elapsed since PHQ started
            time_delta = current_time - session.phq_start_time
            assessment_time = int(time_delta.total_seconds())
            
            # Ensure non-negative time
            return max(0, assessment_time)
    
    @staticmethod 
    def get_llm_assessment_time(session_id: str, current_time: Optional[datetime] = None) -> int:
        """
        Get LLM assessment-relative time in seconds
        Returns seconds elapsed since LLM assessment started
        """
        if current_time is None:
            current_time = datetime.utcnow()
            
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session or not session.llm_start_time:
                return 0
            
            # Calculate seconds elapsed since LLM started
            time_delta = current_time - session.llm_start_time
            assessment_time = int(time_delta.total_seconds())
            
            # Ensure non-negative time
            return max(0, assessment_time)
    
    @staticmethod
    def start_phq_assessment(session_id: str, start_time: Optional[datetime] = None) -> bool:
        """Set PHQ assessment start time"""
        if start_time is None:
            start_time = datetime.utcnow()
            
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                return False
            
            session.phq_start_time = start_time
            db.commit()
            return True
    
    @staticmethod
    def start_llm_assessment(session_id: str, start_time: Optional[datetime] = None) -> bool:
        """Set LLM assessment start time"""
        if start_time is None:
            start_time = datetime.utcnow()
            
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                return False
            
            session.llm_start_time = start_time
            db.commit()
            return True
    
    @staticmethod
    def get_session_start_time(session_id: str) -> Optional[datetime]:
        """Get the session start time"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            return session.start_time if session else None
    
    @staticmethod
    def update_session_start_time(session_id: str, start_time: Optional[datetime] = None) -> bool:
        """Update session start time (used for session resets)"""
        if start_time is None:
            start_time = datetime.utcnow()
            
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                return False
            
            session.start_time = start_time
            db.commit()
            return True