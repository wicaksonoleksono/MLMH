from app.model.assessment.sessions import AssessmentSession
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
        """Check if user can create a new session (max 2 sessions, smart about incomplete)"""
        with get_session() as db:
            # Check for active sessions first
            active_sessions = db.query(AssessmentSession).filter(
                AssessmentSession.user_id == user_id,
                AssessmentSession.status.in_(['CREATED', 'CONSENT', 'CAMERA_CHECK',
                                             'PHQ_IN_PROGRESS', 'LLM_IN_PROGRESS', 'BOTH_IN_PROGRESS'])
            ).count()
            
            # If there are active sessions, cannot create new one
            if active_sessions > 0:
                return False
            
            # Count meaningful sessions (completed + recoverable incomplete)
            completed_sessions = db.query(AssessmentSession).filter(
                AssessmentSession.user_id == user_id,
                AssessmentSession.status == 'COMPLETED'
            ).count()
            
            # If user has 2 completed sessions, they've reached the limit
            if completed_sessions >= SessionService.MAX_SESSIONS_PER_USER:
                return False
            # Note: We removed the recoverable session blocking here because 
            # the /assessment/start route now handles recoverable sessions intelligently
            # by auto-resetting them instead of blocking with errors
            # Count all sessions to enforce total limit
            total_sessions = db.query(AssessmentSession).filter_by(user_id=user_id).count()
            return total_sessions < SessionService.MAX_SESSIONS_PER_USER

    @staticmethod
    def create_session(user_id: int) -> AssessmentSession:
        """Create new session with atomic validation to prevent race conditions"""
        # Double-check session limit with database lock to prevent race conditions
        with get_session() as db:
            # Check for active sessions
            active_sessions = db.query(AssessmentSession).filter(
                AssessmentSession.user_id == user_id,
                AssessmentSession.status.in_(['CREATED', 'CONSENT', 'CAMERA_CHECK',
                                             'PHQ_IN_PROGRESS', 'LLM_IN_PROGRESS', 'BOTH_IN_PROGRESS'])
            ).count()
            
            if active_sessions > 0:
                raise ValueError("Anda sudah memiliki sesi aktif. Selesaikan sesi yang ada terlebih dahulu.")
            
            # Note: Recoverable session check removed - handled at route level by auto-reset
            
            # Check completed sessions limit
            completed_sessions = db.query(AssessmentSession).filter(
                AssessmentSession.user_id == user_id,
                AssessmentSession.status == 'COMPLETED'
            ).count()
            
            if completed_sessions >= SessionService.MAX_SESSIONS_PER_USER:
                raise ValueError("Anda sudah mencapai maksimum 2 sesi assessment yang telah diselesaikan.")
            
            # Final total check
            total_sessions = db.query(AssessmentSession).filter_by(user_id=user_id).count()
            if total_sessions >= SessionService.MAX_SESSIONS_PER_USER:
                raise ValueError("Anda sudah mencapai maksimum 2 sesi assessment.")
        
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
    def get_session(session_id: str) -> Optional[AssessmentSession]:
        """Get session by ID"""
        with get_session() as db:
            return db.query(AssessmentSession).filter_by(id=session_id).first()
    
    @staticmethod
    def validate_user_session(session_id: str, user_id: int) -> bool:
        """Validate session belongs to user - clean SOC validation"""
        session = SessionService.get_session(session_id)
        return session is not None and str(session.user_id) == str(user_id)
    
    # Remove get_session_by_token - UUID serves as both ID and token
    
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
                    status_indicator = ''
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
                    'id': session.id,  # UUID serves as both ID and secure token
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
        """Get user's truly active session (not incomplete/abandoned)"""
        with get_session() as db:
            return db.query(AssessmentSession).filter(
                AssessmentSession.user_id == user_id,
                AssessmentSession.status.in_([
                    'CREATED', 'CONSENT', 'CAMERA_CHECK', 
                    'PHQ_IN_PROGRESS', 'LLM_IN_PROGRESS', 'BOTH_IN_PROGRESS'
                    # Removed 'INCOMPLETE' - incomplete sessions should not block new session creation
                ]),
                AssessmentSession.is_active == True
            ).order_by(AssessmentSession.created_at.desc()).first()
    
    @staticmethod
    def update_consent_data(session_id: str, consent_data: Dict[str, Any]) -> AssessmentSession:
        """Update session with consent data"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            session.complete_consent(consent_data)
            db.commit()
            return session
    
    @staticmethod
    def complete_phq_assessment(session_id: str) -> AssessmentSession:
        """Mark PHQ assessment as completed"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            session.complete_phq()
            db.commit()
            return session
    
    @staticmethod
    def complete_camera_check(session_id: str) -> AssessmentSession:
        """Mark camera check as completed and start first assessment"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            session.complete_camera_check()
            db.commit()
            return session
    
    @staticmethod
    def complete_llm_assessment(session_id: str) -> AssessmentSession:
        """Mark LLM assessment as completed"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            session.complete_llm()
            db.commit()
            return session
    
    @staticmethod
    def complete_phq_and_get_next_step(session_id: str) -> Dict[str, Any]:
        """Complete PHQ assessment and determine next step directly"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            print(f"🔍 PHQ Completion - Before: session_id={session_id}, status={session.status}, phq_completed={session.phq_completed_at}, llm_completed={session.llm_completed_at}")
            
            # Complete PHQ assessment
            session.complete_phq()
            db.commit()
            
            # Get updated session to check status
            updated_session = db.query(AssessmentSession).filter_by(id=session_id).first()
            print(f"🔍 PHQ Completion - After: session_id={session_id}, status={updated_session.status}, phq_completed={updated_session.phq_completed_at}, llm_completed={updated_session.llm_completed_at}")
            
            # Determine next redirect based on session status
            if updated_session.status == 'LLM_IN_PROGRESS':
                next_redirect = '/assessment/llm'
                message = "PHQ selesai! Lanjut ke LLM assessment..."
                print(f" PHQ → LLM: Redirecting to {next_redirect}")
            elif updated_session.status == 'COMPLETED':
                next_redirect = '/assessment/'
                message = "Semua assessment selesai!"
                print(f" Both Complete: Redirecting to {next_redirect}")
            else:
                # Fallback
                next_redirect = '/assessment/'
                message = "PHQ assessment selesai!"
                print(f" Unexpected status {updated_session.status}: Fallback to {next_redirect}")
            
            return {
                "session_id": session_id,
                "assessment_completed": "phq",
                "session_status": updated_session.status,
                "next_redirect": next_redirect,
                "message": message
            }
    
    @staticmethod
    def complete_llm_and_get_next_step(session_id: str) -> Dict[str, Any]:
        """Complete LLM assessment and determine next step directly"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            print(f"🔍 LLM Completion - Before: session_id={session_id}, status={session.status}, phq_completed={session.phq_completed_at}, llm_completed={session.llm_completed_at}")
            
            # Complete LLM assessment
            session.complete_llm()
            db.commit()
            
            # Get updated session to check status
            updated_session = db.query(AssessmentSession).filter_by(id=session_id).first()
            print(f"🔍 LLM Completion - After: session_id={session_id}, status={updated_session.status}, phq_completed={updated_session.phq_completed_at}, llm_completed={updated_session.llm_completed_at}")
            
            # Determine next redirect based on session status
            if updated_session.status == 'PHQ_IN_PROGRESS':
                next_redirect = '/assessment/phq'
                message = "LLM selesai! Lanjut ke PHQ assessment..."
                print(f" LLM → PHQ: Redirecting to {next_redirect}")
            elif updated_session.status == 'COMPLETED':
                next_redirect = '/assessment/'
                message = "Semua assessment selesai! "
                print(f" Both Complete: Redirecting to {next_redirect}")
            else:
                # Fallback
                next_redirect = '/assessment/'
                message = "LLM assessment selesai!"
                print(f" Unexpected status {updated_session.status}: Fallback to {next_redirect}")
            
            return {
                "session_id": session_id,
                "assessment_completed": "llm", 
                "session_status": updated_session.status,
                "next_redirect": next_redirect,
                "message": message
            }
    
    @staticmethod
    def reset_session_to_new_attempt(session_id: str, reason: str = "MANUAL_RESET") -> Dict[str, Any]:
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
            from ..model.assessment.sessions import PHQResponse, LLMConversation, LLMAnalysisResult, CameraCapture
            
            # Get camera capture filenames BEFORE reset (tied to session_id)
            camera_filenames = [capture.filename for capture in db.query(CameraCapture).filter_by(assessment_session_id=session_id).all()]
            
            # Delete physical camera files
            if camera_filenames:
                from ..services.camera.cameraCaptureService import CameraCaptureService
                for filename in camera_filenames:
                    try:
                        CameraCaptureService.delete_capture_file(filename)
                    except Exception as e:
                        print(f" Failed to delete camera capture file {filename}: {e}")
            
            # Delete PHQ responses for this session
            db.query(PHQResponse).filter_by(session_id=session_id).delete()
            
            # Delete LLM conversations for this session
            db.query(LLMConversation).filter_by(session_id=session_id).delete()
            
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
    def delete_session(session_id: str) -> bool:
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
    
