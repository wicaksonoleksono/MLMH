from app.model.assessment.sessions import AssessmentSession, PHQResponse, LLMConversationTurn, CameraCapture
from app.model.admin.phq import PHQSettings
from app.model.admin.llm import LLMSettings
from app.model.admin.camera import CameraSettings
from app.db import get_session
from datetime import datetime
from sqlalchemy import desc, func, and_
from typing import Optional, Dict, Any
import secrets

class SessionService:
    MAX_SESSIONS_PER_USER = 2
    
    @staticmethod
    def get_user_session_count(user_id: int) -> int:
        """Get current session count for user"""
        with get_session() as db:
            return db.query(AssessmentSession).filter_by(user_id=user_id).count()
    
    @staticmethod
    def can_create_session(user_id: int) -> bool:
        """Check if user can create new session"""
        return SessionService.get_user_session_count(user_id) < SessionService.MAX_SESSIONS_PER_USER
    
    @staticmethod
    def create_session(user_id: int) -> AssessmentSession:
        """Create new session with FK references to current admin settings"""
        if not SessionService.can_create_session(user_id):
            raise ValueError(f"User has reached maximum sessions limit ({SessionService.MAX_SESSIONS_PER_USER})")
        
        with get_session() as db:
            # Get current default admin settings
            phq_settings = db.query(PHQSettings).filter_by(is_default=True, is_active=True).first()
            llm_settings = db.query(LLMSettings).filter_by(is_default=True, is_active=True).first()
            camera_settings = db.query(CameraSettings).filter_by(is_default=True, is_active=True).first()
            
            if not phq_settings:
                raise ValueError("No default PHQ settings found")
            if not llm_settings:
                raise ValueError("No default LLM settings found")
            if not camera_settings:
                raise ValueError("No default Camera settings found")
            
            # Get total session count for 50:50 alternating
            total_sessions = db.query(func.count(AssessmentSession.id)).scalar() or 0
            is_first = 'phq' if total_sessions % 2 == 0 else 'llm'
            
            # Generate unique session token
            session_token = secrets.token_urlsafe(32)
            
            session = AssessmentSession(
                user_id=user_id,
                session_token=session_token,
                phq_settings_id=phq_settings.id,
                llm_settings_id=llm_settings.id,
                camera_settings_id=camera_settings.id,
                is_first=is_first,
                status='STARTED'
            )
            db.add(session)
            db.commit()
            return session
    
    @staticmethod
    def get_session(session_id: int) -> Optional[AssessmentSession]:
        """Get session by ID"""
        with get_session() as db:
            return db.query(AssessmentSession).filter_by(id=session_id).first()
    
    @staticmethod
    def get_user_sessions(user_id: int) -> list[AssessmentSession]:
        """Get all sessions for user"""
        with get_session() as db:
            return db.query(AssessmentSession).filter_by(user_id=user_id).order_by(desc(AssessmentSession.created_at)).all()
    
    @staticmethod
    def get_active_session(user_id: int) -> Optional[AssessmentSession]:
        """Get user's incomplete session if exists"""
        with get_session() as db:
            return db.query(AssessmentSession).filter(
                AssessmentSession.user_id == user_id,
                AssessmentSession.status != 'COMPLETED'
            ).first()
    
    @staticmethod
    def update_consent_data(session_id: int, consent_data: Dict[str, Any]) -> AssessmentSession:
        """Update session with consent data"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            session.complete_consent(consent_data)
            db.commit()
            return session
    
    @staticmethod
    def complete_phq_assessment(session_id: int) -> AssessmentSession:
        """Mark PHQ assessment as completed"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            session.complete_phq()
            db.commit()
            return session
    
    @staticmethod
    def complete_llm_assessment(session_id: int) -> AssessmentSession:
        """Mark LLM assessment as completed"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            session.complete_llm()
            db.commit()
            return session
    
    @staticmethod
    def delete_session(session_id: int) -> bool:
        """Delete session"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            db.delete(session)
            db.commit()
            return True
    
    @staticmethod
    def get_all_sessions(page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Get all sessions with pagination (admin)"""
        with get_session() as db:
            sessions = db.query(AssessmentSession).order_by(desc(AssessmentSession.created_at)).offset((page-1)*per_page).limit(per_page).all()
            total = db.query(func.count(AssessmentSession.id)).scalar()
            return {'sessions': sessions, 'total': total, 'page': page, 'per_page': per_page}
    
    @staticmethod
    def get_sessions_by_status(status: str, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Get sessions by status (admin)"""
        with get_session() as db:
            sessions = db.query(AssessmentSession).filter_by(status=status).order_by(desc(AssessmentSession.created_at)).offset((page-1)*per_page).limit(per_page).all()
            total = db.query(func.count(AssessmentSession.id)).filter_by(status=status).scalar()
            return {'sessions': sessions, 'total': total, 'page': page, 'per_page': per_page}