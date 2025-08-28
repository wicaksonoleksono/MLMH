from app.model.assessment.sessions import AssessmentSession, PHQResponse, LLMConversationTurn
from app.db import get_session
from datetime import datetime
from sqlalchemy import desc, func
from typing import Optional, Dict, Any

# Import new session management services
from .session.sessionManager import SessionManager
from .session.assessmentOrchestrator import AssessmentOrchestrator

"""
Session Service - Clean and Simple

Core session management for mental health assessments:
- Session creation and lifecycle
- Direct session state management  
- Assessment completion tracking
- Simple, straightforward flow
"""

class SessionService:
    MAX_SESSIONS_PER_USER = 2
    
    @staticmethod
    def check_assessment_settings_configured() -> dict:
        """Check if all required assessment settings are configured - delegate to SessionManager"""
        return SessionManager.check_assessment_settings_configured()
    
    @staticmethod
    def is_session_valid(session: AssessmentSession) -> bool:
        """Check if session is valid (completed successfully)"""
        return session.status == 'COMPLETED' and session.is_completed
    
    
    @staticmethod
    def get_valid_user_sessions(user_id: int) -> list[AssessmentSession]:
        """Get only valid (completed) sessions for user"""
        with get_session() as db:
            return db.query(AssessmentSession).filter(
                AssessmentSession.user_id == user_id,
                AssessmentSession.status == 'COMPLETED',
                AssessmentSession.is_completed == True
            ).order_by(desc(AssessmentSession.created_at)).all()
    
    @staticmethod
    def get_user_session_count(user_id: int) -> int:
        """DEPRECATED - Get current session count for user - use SessionManager methods instead"""
        with get_session() as db:
            return db.query(AssessmentSession).filter_by(user_id=user_id).count()
    
    @staticmethod
    def can_create_session(user_id: int) -> bool:
        """Check if user can create new session - delegate to SessionManager"""
        return SessionManager.can_create_session(user_id)
    
    @staticmethod
    def create_session(user_id: int) -> AssessmentSession:
        """Create new session with improved recovery handling - NO MORE NUCLEAR CLEANUP"""
        # Use new SessionManager for clean session creation
        session = SessionManager.create_new_session(user_id)
        
        # Initialize assessments data (pre-generate questions and context)
        try:
            initialization_result = AssessmentOrchestrator.initialize_session_assessments(session.id)
            if not initialization_result['ready_for_assessments']:
                # Log warning but don't fail session creation
                print(f"Warning: Session {session.id} created but assessments not fully initialized")
        except Exception as e:
            print(f"Warning: Failed to initialize assessments for session {session.id}: {e}")
        
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
    def get_user_sessions_with_status(user_id: int) -> list[dict]:
        """Get user sessions with human-readable status indicators"""
        with get_session() as db:
            sessions = db.query(AssessmentSession).filter_by(user_id=user_id).order_by(desc(AssessmentSession.created_at)).all()
            
            result = []
            for session in sessions:
                # Determine status display
                if session.status == 'COMPLETED':
                    status_indicator = '✅'
                    status_text = 'Berhasil'
                    status_class = 'success'
                elif session.status == 'FAILED':
                    status_indicator = '❌'
                    status_text = 'Gagal'
                    status_class = 'failed'
                elif session.status in ['ABANDONED', 'INCOMPLETE']:
                    status_indicator = '⏸️'
                    status_text = 'Tidak Selesai'
                    status_class = 'abandoned'
                elif session.status in ['PHQ_IN_PROGRESS', 'LLM_IN_PROGRESS']:
                    status_indicator = '🔄'
                    status_text = 'Sedang Berlangsung'
                    status_class = 'in_progress'
                else:  # CREATED, CONSENT
                    status_indicator = '⏳'
                    status_text = 'Belum Dimulai'
                    status_class = 'pending'
                
                # Determine what's completed
                completed_assessments = []
                if session.phq_completed_at:
                    completed_assessments.append('PHQ')
                if session.llm_completed_at:
                    completed_assessments.append('LLM')
                
                result.append({
                    'id': session.id,
                    'status': session.status,
                    'status_indicator': status_indicator,
                    'status_text': status_text,
                    'status_class': status_class,
                    'completion_percentage': session.completion_percentage,
                    'completed_assessments': completed_assessments,
                    'failure_reason': session.failure_reason,
                    'is_first': session.is_first,
                    'created_at': session.created_at,
                    'completed_at': session.end_time,
                    'duration_minutes': session.duration_seconds // 60 if session.duration_seconds else None,
                    'consent_completed': session.consent_completed_at is not None,
                    'phq_completed': session.phq_completed_at is not None,
                    'llm_completed': session.llm_completed_at is not None
                })
            
            return result
    
    @staticmethod
    def get_active_session(user_id: int) -> Optional[AssessmentSession]:
        """Get user's active/incomplete session if exists"""
        with get_session() as db:
            return db.query(AssessmentSession).filter(
                AssessmentSession.user_id == user_id,
                AssessmentSession.status.in_([
                    'CREATED', 'CONSENT', 'CAMERA_CHECK', 
                    'PHQ_IN_PROGRESS', 'LLM_IN_PROGRESS', 'BOTH_IN_PROGRESS',
                    'INCOMPLETE'  # Include incomplete for recovery scenarios
                ]),
                AssessmentSession.is_active == True
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
    def complete_camera_check(session_id: int) -> AssessmentSession:
        """Mark camera check as completed and start first assessment"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            session.complete_camera_check()
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
    
