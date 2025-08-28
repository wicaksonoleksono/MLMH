# app/services/session/assessmentOrchestrator.py
from typing import Optional, Dict, Any, List
from datetime import datetime
from ...model.assessment.sessions import AssessmentSession
from ...model.admin.phq import PHQQuestion, PHQSettings, PHQCategoryType
from ...model.admin.llm import LLMSettings
from ...db import get_session
import random


class AssessmentOrchestrator:
    """Coordinate PHQ + LLM assessment flow with proper coupling and pre-generation"""
    
    @staticmethod
    def initialize_session_assessments(session_id: int) -> Dict[str, Any]:
        """Pre-generate both PHQ questions and LLM context when session starts"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            results = {}
            
            # Initialize PHQ assessment data
            phq_result = AssessmentOrchestrator._initialize_phq_questions(session, db)
            results['phq'] = phq_result
            
            # Initialize LLM assessment context
            llm_result = AssessmentOrchestrator._initialize_llm_context(session, db)
            results['llm'] = llm_result
            
            # Update session metadata with generation status
            if not session.assessment_order:
                session.assessment_order = {'first': session.is_first, 'second': 'llm' if session.is_first == 'phq' else 'phq'}
            
            session.assessment_order['phq_questions_generated'] = phq_result['generated']
            session.assessment_order['llm_context_initialized'] = llm_result['initialized']
            session.assessment_order['generation_timestamp'] = datetime.utcnow().isoformat()
            
            db.commit()
            
            return {
                'session_id': session.id,
                'assessment_order': session.assessment_order,
                'phq_initialized': phq_result['generated'],
                'llm_initialized': llm_result['initialized'],
                'ready_for_assessments': phq_result['generated'] and llm_result['initialized'],
                'phq_questions_count': phq_result.get('questions_count', 0),
                'llm_aspects_count': llm_result.get('aspects_count', 0)
            }
    
    @staticmethod
    def _initialize_phq_questions(session: AssessmentSession, db) -> Dict[str, Any]:
        """Pre-generate randomized PHQ questions for the session"""
        try:
            phq_settings = session.phq_settings
            if not phq_settings:
                return {'generated': False, 'error': 'PHQ settings not found'}
            
            # Get all available categories
            categories = PHQCategoryType.get_all_categories()
            questions_per_category = phq_settings.questions_per_category
            
            session_questions = []
            total_questions = 0
            
            for category in categories:
                # Get all questions for this category
                category_questions = db.query(PHQQuestion).filter(
                    PHQQuestion.category_name_id == category['name_id'],
                    PHQQuestion.is_active == True
                ).all()
                
                if len(category_questions) < questions_per_category:
                    # Not enough questions in this category
                    selected_questions = category_questions
                else:
                    # Randomly select required number of questions
                    selected_questions = random.sample(category_questions, questions_per_category)
                
                # Store question metadata for session
                for idx, question in enumerate(selected_questions):
                    session_questions.append({
                        'question_id': question.id,
                        'category_name_id': category['name_id'],
                        'category_display_name': category['display_name'],
                        'question_text_id': question.question_text_id,
                        'question_text_en': question.question_text_en,
                        'order_index': question.order_index,
                        'session_order': total_questions + idx + 1
                    })
                
                total_questions += len(selected_questions)
            
            # Randomize question order if required
            if phq_settings.randomize_categories:
                random.shuffle(session_questions)
            
            # Store in session metadata
            if not session.session_metadata:
                session.session_metadata = {}
            
            session.session_metadata['phq_questions'] = session_questions
            session.session_metadata['phq_questions_generated_at'] = datetime.utcnow().isoformat()
            session.session_metadata['phq_scale_id'] = phq_settings.scale_id
            session.session_metadata['phq_instructions'] = phq_settings.instructions
            
            return {
                'generated': True,
                'questions_count': total_questions,
                'categories_count': len(categories),
                'randomized': phq_settings.randomize_categories
            }
            
        except Exception as e:
            return {'generated': False, 'error': str(e)}
    
    @staticmethod
    def _initialize_llm_context(session: AssessmentSession, db) -> Dict[str, Any]:
        """Initialize LLM conversation context with depression aspects"""
        try:
            llm_settings = session.llm_settings
            if not llm_settings:
                return {'initialized': False, 'error': 'LLM settings not found'}
            
            # Extract depression aspects
            aspects = []
            if llm_settings.depression_aspects and 'aspects' in llm_settings.depression_aspects:
                aspects = llm_settings.depression_aspects['aspects']
            
            # Store in session metadata
            if not session.session_metadata:
                session.session_metadata = {}
            
            session.session_metadata['llm_aspects'] = aspects
            session.session_metadata['llm_context_initialized_at'] = datetime.utcnow().isoformat()
            session.session_metadata['llm_chat_model'] = llm_settings.chat_model
            session.session_metadata['llm_analysis_model'] = llm_settings.analysis_model
            session.session_metadata['llm_instructions'] = llm_settings.instructions
            
            return {
                'initialized': True,
                'aspects_count': len(aspects),
                'chat_model': llm_settings.chat_model,
                'analysis_model': llm_settings.analysis_model
            }
            
        except Exception as e:
            return {'initialized': False, 'error': str(e)}
    
    @staticmethod
    def get_session_phq_questions(session_id: int) -> List[Dict[str, Any]]:
        """Get pre-generated PHQ questions for a session"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            if not (session.session_metadata and 'phq_questions' in session.session_metadata):
                # Questions not pre-generated, initialize now
                AssessmentOrchestrator.initialize_session_assessments(session_id)
                # Refresh session
                session = db.query(AssessmentSession).filter_by(id=session_id).first()
            
            questions = session.session_metadata.get('phq_questions', [])
            instructions = session.session_metadata.get('phq_instructions', '')
            scale_id = session.session_metadata.get('phq_scale_id')
            
            return {
                'questions': questions,
                'total_questions': len(questions),
                'instructions': instructions,
                'scale_id': scale_id,
                'generated_at': session.session_metadata.get('phq_questions_generated_at')
            }
    
    @staticmethod
    def get_session_llm_context(session_id: int) -> Dict[str, Any]:
        """Get pre-initialized LLM context for a session"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            if not (session.session_metadata and 'llm_aspects' in session.session_metadata):
                # Context not initialized, initialize now
                AssessmentOrchestrator.initialize_session_assessments(session_id)
                # Refresh session
                session = db.query(AssessmentSession).filter_by(id=session_id).first()
            
            return {
                'aspects': session.session_metadata.get('llm_aspects', []),
                'chat_model': session.session_metadata.get('llm_chat_model'),
                'analysis_model': session.session_metadata.get('llm_analysis_model'),
                'instructions': session.session_metadata.get('llm_instructions'),
                'initialized_at': session.session_metadata.get('llm_context_initialized_at')
            }
    
    @staticmethod
    def handle_assessment_completion(session_id: int, assessment_type: str) -> Dict[str, Any]:
        """Handle completion of one assessment and determine next steps"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            # Update completion timestamp
            if assessment_type == 'phq':
                session.phq_completed_at = datetime.utcnow()
            elif assessment_type == 'llm':
                session.llm_completed_at = datetime.utcnow()
            
            # Determine next steps based on completion state
            next_action = AssessmentOrchestrator._determine_next_action(session)
            
            # Update session status
            session.status = next_action['status']
            session.update_completion_percentage()
            session.updated_at = datetime.utcnow()
            
            db.commit()
            
            return {
                'session_id': session.id,
                'completed_assessment': assessment_type,
                'next_action': next_action,
                'completion_percentage': session.completion_percentage,
                'both_completed': session.phq_completed_at is not None and session.llm_completed_at is not None
            }
    
    @staticmethod
    def _determine_next_action(session: AssessmentSession) -> Dict[str, Any]:
        """Determine what should happen next based on current completion state"""
        phq_done = session.phq_completed_at is not None
        llm_done = session.llm_completed_at is not None
        
        if phq_done and llm_done:
            # Both assessments completed - session is done
            return {
                'status': 'COMPLETED',
                'next_step': 'completed',
                'message': 'Both assessments completed successfully'
            }
        elif phq_done and not llm_done:
            # PHQ done, need LLM
            return {
                'status': 'LLM_IN_PROGRESS',
                'next_step': 'llm',
                'message': 'PHQ completed, proceed to LLM assessment'
            }
        elif llm_done and not phq_done:
            # LLM done, need PHQ
            return {
                'status': 'PHQ_IN_PROGRESS',
                'next_step': 'phq',
                'message': 'LLM completed, proceed to PHQ assessment'
            }
        else:
            # Neither done yet, continue with current
            if session.status == 'PHQ_IN_PROGRESS':
                return {
                    'status': 'PHQ_IN_PROGRESS',
                    'next_step': 'phq',
                    'message': 'Continue PHQ assessment'
                }
            else:
                return {
                    'status': 'LLM_IN_PROGRESS',
                    'next_step': 'llm',
                    'message': 'Continue LLM assessment'
                }
    
    @staticmethod
    def restart_coupled_assessments(session_id: int, reason: str = None) -> Dict[str, Any]:
        """Restart both assessments due to coupling requirement - key feature"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            # Clear all assessment data due to coupling
            from ...model.assessment.sessions import PHQResponse, LLMConversationTurn
            
            # Delete existing responses
            db.query(PHQResponse).filter_by(session_id=session_id).delete()
            db.query(LLMConversationTurn).filter_by(session_id=session_id).delete()
            
            # Reset completion timestamps
            session.phq_completed_at = None
            session.llm_completed_at = None
            
            # Reset to camera check (preserve consent)
            session.status = 'CAMERA_CHECK'
            session.incomplete_reason = reason or "Both assessments restarted due to coupling requirement"
            
            # Regenerate assessment data
            session.session_metadata['phq_questions'] = None
            session.session_metadata['llm_aspects'] = None
            session.assessment_order['phq_questions_generated'] = False
            session.assessment_order['llm_context_initialized'] = False
            
            session.updated_at = datetime.utcnow()
            
            db.commit()
            
            return {
                'session_id': session.id,
                'status': session.status,
                'message': 'Both assessments restarted due to coupling requirement',
                'data_cleared': True,
                'next_step': 'camera_check'
            }