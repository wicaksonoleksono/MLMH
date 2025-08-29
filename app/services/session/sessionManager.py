# app/services/session/sessionManager.py
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy import func
from ...model.assessment.sessions import AssessmentSession
from ...model.admin.phq import PHQSettings
from ...model.admin.llm import LLMSettings
from ...model.admin.camera import CameraSettings
from ...db import get_session
import uuid
import hashlib


class SessionManager:
    """Core session lifecycle management with proper separation of concerns"""

    MAX_SESSIONS_PER_USER = 2

    @staticmethod
    def check_assessment_settings_configured() -> Dict[str, Any]:
        """Check if all required assessment settings are configured and complete"""
        with get_session() as db:
            from ...model.admin.phq import PHQQuestion
            
            # Get active settings
            phq_settings = db.query(PHQSettings).filter_by(is_active=True).first()
            llm_settings = db.query(LLMSettings).filter_by(is_active=True).first()
            camera_settings = db.query(CameraSettings).filter_by(is_active=True).first()
            
            # Validate PHQ settings completeness
            phq_valid = False
            if phq_settings:
                # Check if PHQ questions exist
                phq_questions_count = db.query(PHQQuestion).filter_by(is_active=True).count()
                phq_valid = phq_questions_count > 0
            
            # Validate LLM settings completeness  
            llm_valid = False
            if llm_settings:
                # Check API key not empty and depression aspects exist
                api_key_valid = (llm_settings.openai_api_key and 
                               llm_settings.openai_api_key.strip() != '')
                aspects_valid = (llm_settings.depression_aspects and 
                               isinstance(llm_settings.depression_aspects, dict) and 
                               llm_settings.depression_aspects.get('aspects') and
                               len(llm_settings.depression_aspects.get('aspects', [])) > 0)
                llm_valid = api_key_valid and aspects_valid
            
            # Camera settings just need to exist (basic validation)
            camera_valid = camera_settings is not None
            
            # Collect missing/invalid settings
            missing_settings = []
            if not phq_valid:
                if not phq_settings:
                    missing_settings.append('PHQ Settings (belum dibuat)')
                else:
                    missing_settings.append('PHQ Questions (pertanyaan belum diset)')
            
            if not llm_valid:
                if not llm_settings:
                    missing_settings.append('LLM Settings (belum dibuat)')
                else:
                    if not (llm_settings.openai_api_key and llm_settings.openai_api_key.strip()):
                        missing_settings.append('OpenAI API Key (kosong)')
                    if not (llm_settings.depression_aspects and 
                           llm_settings.depression_aspects.get('aspects') and
                           len(llm_settings.depression_aspects.get('aspects', [])) > 0):
                        missing_settings.append('Depression Aspects (aspek belum diset)')
            
            if not camera_valid:
                missing_settings.append('Camera Settings (belum dibuat)')

            return {
                'all_configured': all([phq_valid, llm_valid, camera_valid]),
                'phq_configured': phq_valid,
                'llm_configured': llm_valid,
                'camera_configured': camera_valid,
                'missing_settings': missing_settings
            }

    @staticmethod
    def can_create_session(user_id: int) -> bool:
        """Check if user can create new session (considering active sessions only)"""
        with get_session() as db:
            active_sessions = db.query(AssessmentSession).filter(
                AssessmentSession.user_id == user_id,
                AssessmentSession.status.in_(['CREATED', 'CONSENT', 'CAMERA_CHECK',
                                             'PHQ_IN_PROGRESS', 'LLM_IN_PROGRESS', 'BOTH_IN_PROGRESS'])
            ).count()
            return active_sessions < SessionManager.MAX_SESSIONS_PER_USER

    @staticmethod
    def get_user_active_session(user_id: int) -> Optional[AssessmentSession]:
        """Get user's active session if exists"""
        with get_session() as db:
            return db.query(AssessmentSession).filter(
                AssessmentSession.user_id == user_id,
                AssessmentSession.status.in_(['CREATED', 'CONSENT', 'CAMERA_CHECK',
                                             'PHQ_IN_PROGRESS', 'LLM_IN_PROGRESS', 'BOTH_IN_PROGRESS'])
            ).first()

    @staticmethod
    def get_user_recoverable_session(user_id: int) -> Optional[AssessmentSession]:
        """Get user's most recent recoverable session (INCOMPLETE or ABANDONED)"""
        with get_session() as db:
            return db.query(AssessmentSession).filter(
                AssessmentSession.user_id == user_id,
                AssessmentSession.status.in_(['INCOMPLETE', 'ABANDONED']),
                AssessmentSession.can_recover == True
            ).order_by(AssessmentSession.updated_at.desc()).first()

    @staticmethod
    def get_user_incomplete_session(user_id: int) -> Optional[AssessmentSession]:
        """Get user's incomplete session that can be recovered (backward compatibility)"""
        return SessionManager.get_user_recoverable_session(user_id)

    @staticmethod
    def create_new_session(user_id: int) -> AssessmentSession:
        """Create a new assessment session with proper initialization"""
        # Check if user can create session
        if not SessionManager.can_create_session(user_id):
            raise ValueError(f"User has reached maximum active sessions limit ({SessionManager.MAX_SESSIONS_PER_USER})")

        # Check if all assessment settings are configured
        settings_check = SessionManager.check_assessment_settings_configured()
        if not settings_check['all_configured']:
            missing = ', '.join(settings_check['missing_settings'])
            raise ValueError(f"Pengaturan assessment belum lengkap. Missing: {missing}")

        with get_session() as db:
            # Get active admin settings
            phq_settings = db.query(PHQSettings).filter_by(is_active=True).first()
            llm_settings = db.query(LLMSettings).filter_by(is_active=True).first()
            camera_settings = db.query(CameraSettings).filter_by(is_active=True).first()

            # Get session number for this user (1 or 2)
            user_session_count = db.query(func.count(AssessmentSession.id)).filter_by(user_id=user_id).scalar() or 0
            session_number = user_session_count + 1

            # Generate unique UUID for session
            session_id = str(uuid.uuid4())
            
            # Determine assessment order (50:50 deterministic based on user_id hash)
            # This ensures same user gets same pattern but overall distribution is 50:50
            user_hash = hashlib.md5(str(user_id).encode()).hexdigest()
            is_first = 'phq' if int(user_hash[-1], 16) % 2 == 0 else 'llm'

            # Create session with assessment order metadata
            assessment_order = {
                'first': is_first,
                'second': 'llm' if is_first == 'phq' else 'phq',
                'phq_questions_generated': False,
                'llm_context_initialized': False
            }

            session = AssessmentSession(
                id=session_id,
                user_id=user_id,
                phq_settings_id=phq_settings.id,
                llm_settings_id=llm_settings.id,
                camera_settings_id=camera_settings.id,
                is_first=is_first,
                status='CREATED',
                assessment_order=assessment_order,
                session_number=session_number
            )

            db.add(session)
            db.commit()
            return session

    @staticmethod
    def transition_session_status(session_id: int, new_status: str) -> AssessmentSession:
        """Transition session to new status with proper validation"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")

            # Validate status transition
            valid_transitions = {
                'CREATED': ['CONSENT', 'INCOMPLETE', 'ABANDONED'],
                'CONSENT': ['CAMERA_CHECK', 'INCOMPLETE', 'ABANDONED'],
                'CAMERA_CHECK': ['PHQ_IN_PROGRESS', 'LLM_IN_PROGRESS', 'INCOMPLETE', 'ABANDONED'],
                'PHQ_IN_PROGRESS': ['LLM_IN_PROGRESS', 'BOTH_IN_PROGRESS', 'INCOMPLETE', 'ABANDONED'],
                'LLM_IN_PROGRESS': ['PHQ_IN_PROGRESS', 'BOTH_IN_PROGRESS', 'INCOMPLETE', 'ABANDONED'],
                'BOTH_IN_PROGRESS': ['COMPLETED', 'INCOMPLETE', 'ABANDONED'],
                'INCOMPLETE': ['PHQ_IN_PROGRESS', 'LLM_IN_PROGRESS', 'ABANDONED'],
                'COMPLETED': [],  # Final state
                'ABANDONED': []   # Final state
            }

            if new_status not in valid_transitions.get(session.status, []):
                raise ValueError(f"Invalid status transition from {session.status} to {new_status}")

            session.status = new_status
            session.updated_at = datetime.utcnow()

            # Update completion percentage
            session.update_completion_percentage()

            # Handle final states
            if new_status == 'COMPLETED':
                session.complete_session()
            elif new_status == 'INCOMPLETE':
                session.mark_incomplete("Session marked incomplete")
            elif new_status == 'ABANDONED':
                session.mark_incomplete("Session abandoned")

            db.commit()
            return session

    @staticmethod
    def get_session_progress(session_id: str) -> Dict[str, Any]:
        """Get detailed session progress information"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")

            return {
                'session_id': session.id,
                'status': session.status,
                'assessment_order': session.assessment_order,
                'completion_percentage': session.completion_percentage,
                'steps_completed': {
                    'consent': session.consent_completed_at is not None,
                    'camera_check': session.session_metadata and session.session_metadata.get('camera_completed_at') is not None,
                    'phq': session.phq_completed_at is not None,
                    'llm': session.llm_completed_at is not None
                },
                'next_step': SessionManager._determine_next_step(session),
                'created_at': session.created_at,
                'updated_at': session.updated_at
            }

    @staticmethod
    def _determine_next_step(session: AssessmentSession) -> str:
        """Determine what the next step should be for the session"""
        if session.status == 'CREATED':
            return 'consent'
        elif session.status == 'CONSENT':
            return 'camera_check'
        elif session.status == 'CAMERA_CHECK':
            return session.is_first
        elif session.status in ['PHQ_IN_PROGRESS', 'LLM_IN_PROGRESS']:
            # Determine which assessment should be next
            if session.phq_completed_at and not session.llm_completed_at:
                return 'llm'
            elif session.llm_completed_at and not session.phq_completed_at:
                return 'phq'
            else:
                return session.is_first  # Continue current assessment
        elif session.status == 'BOTH_IN_PROGRESS':
            return 'finalize'
        elif session.status == 'COMPLETED':
            return 'completed'
        else:
            return 'unknown'

    @staticmethod
    def recover_session(session_id: str, clear_data: bool = True) -> AssessmentSession:
        """Recover an abandoned/incomplete session"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")

            if not session.can_be_recovered():
                raise ValueError(f"Session {session_id} cannot be recovered (status: {session.status})")

            if clear_data:
                # Clear all assessment data to restart fresh
                from ...model.assessment.sessions import PHQResponse, LLMConversationTurn

                # Delete existing responses
                db.query(PHQResponse).filter_by(session_id=session_id).delete()
                db.query(LLMConversationTurn).filter_by(session_id=session_id).delete()

                # Clear session assessment data
                session.clear_assessment_data()
            else:
                # Just reactivate the session without clearing data
                session.is_active = True
                session.status = session.status if session.status not in ['INCOMPLETE', 'ABANDONED'] else 'CAMERA_CHECK'
                session.updated_at = datetime.utcnow()

            db.commit()
            return session

    @staticmethod
    def abandon_session(session_id: str, reason: str = None) -> AssessmentSession:
        """Mark session as abandoned (user quit)"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")

            session.mark_abandoned(reason or "User abandoned session")
            db.commit()
            return session

    @staticmethod
    def get_session(session_id: str) -> Optional[AssessmentSession]:
        """Get session by ID"""
        with get_session() as db:
            return db.query(AssessmentSession).filter_by(id=session_id).first()
