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
    def can_create_session(user_id: int) -> bool:
        """Check if user can create new session - delegate to SessionManager"""
        return SessionManager.can_create_session(user_id)
    
    @staticmethod
    def get_user_session_count(user_id: int) -> int:
        """Get total number of sessions for a user"""
        with get_session() as db:
            return db.query(AssessmentSession).filter_by(user_id=user_id).count()
    
    @staticmethod
    def can_create_new_session(user_id: int) -> bool:
        """Check if user can create a new session (max 2 sessions)"""
        return SessionService.get_user_session_count(user_id) < 2

    @staticmethod
    def create_session(user_id: int) -> AssessmentSession:
        """Create new session with improved recovery handling - NO MORE NUCLEAR CLEANUP"""
        # Check session limit first
        if not SessionService.can_create_new_session(user_id):
            raise ValueError("User sudah mencapai maksimum 2 session")
        
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
    def get_session_by_token(session_token: str) -> Optional[AssessmentSession]:
        """Get session by secure token"""
        with get_session() as db:
            return db.query(AssessmentSession).filter_by(session_token=session_token).first()
    
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
                # Simplified status display - only "Berhasil" or "Gagal" for users
                if session.status == 'COMPLETED':
                    status_indicator = '✅'
                    status_text = 'Berhasil'
                    status_class = 'success'
                else:
                    # All other statuses show as "Gagal" for users
                    status_indicator = '❌'
                    status_text = 'Gagal'
                    status_class = 'failed'
                
                # Determine what's completed
                completed_assessments = []
                if session.phq_completed_at:
                    completed_assessments.append('PHQ')
                if session.llm_completed_at:
                    completed_assessments.append('LLM')
                
                result.append({
                    'id': session.id,
                    'session_token': session.session_token,  # Add secure token for operations
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
                    'llm_completed': session.llm_completed_at is not None,
                    # Session versioning fields
                    'session_number': getattr(session, 'session_number', 1),
                    'session_display_name': getattr(session, 'session_display_name', f'Sesi #{session.id}'),
                    'session_attempt': session.session_attempt,
                    'reset_count': session.reset_count,
                    'can_reset': session.can_reset_to_new_attempt() if hasattr(session, 'can_reset_to_new_attempt') else False
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
    def reset_session_to_new_attempt(session_id: int, reason: str = "MANUAL_RESET") -> Dict[str, Any]:
        """Reset session to new attempt with version increment"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            if not session.can_reset_to_new_attempt():
                raise ValueError("Session sudah selesai dan tidak dapat direset")
            
            # Store previous attempt for logging
            previous_attempt = session.session_attempt
            
            # Reset to new attempt
            reset_success = session.reset_to_new_attempt(reason)
            if not reset_success:
                raise RuntimeError("Failed to reset session to new attempt")
            
            # Clear related data (PHQ responses, LLM conversations, etc.)
            from ..model.assessment.phq import PHQResponse
            from ..model.assessment.llm import LLMConversationTurn, LLMAnalysisResult
            
            # Delete PHQ responses for this session
            db.query(PHQResponse).filter_by(session_id=session_id).delete()
            
            # Delete LLM conversations for this session
            db.query(LLMConversationTurn).filter_by(session_id=session_id).delete()
            
            # Delete LLM analysis results for this session
            db.query(LLMAnalysisResult).filter_by(session_id=session_id).delete()
            
            db.commit()
            
            return {
                "session_id": session_id,
                "previous_attempt": previous_attempt,
                "current_attempt": session.session_attempt,
                "reset_reason": reason,
                "reset_at": session.last_reset_at.isoformat(),
                "status": session.status,
                "can_reset_again": session.can_reset_to_new_attempt(),
                "session_number": session.session_number,
                "session_display_name": session.session_display_name,
                "message": f"Session reset dalam {session.session_display_name}, percobaan ke-{session.session_attempt}"
            }

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
    
