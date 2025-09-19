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

            # Update session metadata with generation status and flow planning
            if not session.assessment_order:
                second_assessment = 'llm' if session.is_first == 'phq' else 'phq'
                session.assessment_order = {
                    'first': session.is_first,
                    'second': second_assessment,
                    'flow_plan': {
                        f'{session.is_first}_complete_redirect': f'/assessment/{second_assessment}',
                        f'{second_assessment}_complete_redirect': '/assessment/',
                        'both_complete_redirect': '/assessment/'
                    }
                }

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
        """Initialize LLM conversation context with depression aspects and chat history"""
        try:
            llm_settings = session.llm_settings
            if not llm_settings:
                return {'initialized': False, 'error': 'LLM settings not found'}

            # Extract depression aspects
            aspects = []
            if llm_settings.depression_aspects and 'aspects' in llm_settings.depression_aspects:
                aspects = llm_settings.depression_aspects['aspects']

            # Format aspects for the prompt
            formatted_aspects = '\n'.join([f"{aspect['name']} ({aspect['description']})" for aspect in aspects])

            # Create the proper Indonesian system prompt
            system_prompt = f"""Anda adalah Anisa, seorang mahasiswa psikologi yang supportive dan senang hati mendengarkan curhatan orang lain. Teman anda kemungkinan mengalami gejala depresi, atau bisa jadi tidak.
Buatlah beberapa pertanyaan dengan gaya non formal kepada rekan anda tentang aktivitas sehari-hari atau tentang kejadian yang akhir-akhir ini dialami. Tindak lanjuti setiap jawaban dengan pertanyaan yang lebih dalam. Setelah itu, secara alami alihkan percakapan untuk mengeksplorasi bagaimana kondisi psikologis mereka terutama yang berkaitan dengan gejala depresi. Berikut adalah indikator-indikator dari gejala depresi:
{formatted_aspects}
Nanti jika sudah didapatkan semua informasi yang perlu didapatkan Tolong stop ya dengan menutup. Percakapan dengan "gak papa kamu pasti bisa kok, semangat yaa ! Kalau memang darurat deh Hubungi psikolog terdekat mu !!" Tidak perlu bilang secara eksplisit menyebutkan mengenai depresi atau sejenisnya. Kemudian tulis </end_conversation> pada akhir kalimat"""

            # Store in session metadata
            if not session.session_metadata:
                session.session_metadata = {}

            session.session_metadata['llm_aspects'] = aspects
            session.session_metadata['llm_context_initialized_at'] = datetime.utcnow().isoformat()
            session.session_metadata['llm_chat_model'] = llm_settings.chat_model
            session.session_metadata['llm_analysis_model'] = llm_settings.analysis_model
            session.session_metadata['llm_instructions'] = llm_settings.instructions

            # Initialize chat history structure
            session.session_metadata['chat_history'] = {
                'messages': [],
                'conversation_history': [],
                'exchange_count': 0,
                'conversation_active': False,
                'started_at': None,
                'completed_at': None,
                'system_prompt': system_prompt,
                'total_turns': 0
            }

            return {
                'initialized': True,
                'aspects_count': len(aspects),
                'chat_model': llm_settings.chat_model,
                'analysis_model': llm_settings.analysis_model,
                'chat_history_initialized': True
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

            # Store previous completion state
            phq_was_completed = session.phq_completed_at is not None
            llm_was_completed = session.llm_completed_at is not None

            # Update completion timestamp using proper completion methods to ensure timing is tracked correctly
            if assessment_type == 'phq':
                session.complete_phq()
            elif assessment_type == 'llm':
                session.complete_llm()

            # If session was already completed before, ensure duration is properly calculated
            if (phq_was_completed and llm_was_completed) and session.start_time and not session.duration_seconds:
                session.complete_session()

            # Determine next steps based on completion state
            next_action = AssessmentOrchestrator._determine_next_action(session)

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
            from ...model.assessment.sessions import PHQResponse, LLMConversation

            # Delete existing responses
            db.query(PHQResponse).filter_by(session_id=session_id).delete()
            db.query(LLMConversation).filter_by(session_id=session_id).delete()

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

    # ============================================================================
    # LLM CHAT MANAGEMENT METHODS
    # ============================================================================
    
    @staticmethod
    def start_llm_conversation(session_id: int) -> Dict[str, Any]:
        """Start LLM conversation - mark as active and set start time"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            # Ensure chat history is initialized
            if not session.session_metadata or 'chat_history' not in session.session_metadata:
                # Initialize if missing
                AssessmentOrchestrator._initialize_llm_context(session, db)
            
            # Mark conversation as active
            chat_history = session.session_metadata.get('chat_history', {})
            chat_history['conversation_active'] = True
            chat_history['started_at'] = datetime.utcnow().isoformat()
            
            # Save to session_metadata
            session.session_metadata['chat_history'] = chat_history
            session.updated_at = datetime.utcnow()
            db.commit()
            
            return {
                'session_id': session.id,
                'conversation_started': True,
                'system_prompt': chat_history.get('system_prompt', ''),
                'message_count': len(chat_history.get('messages', []))
            }
    
    @staticmethod
    def add_chat_message(session_id: int, message_type: str, content: str) -> Dict[str, Any]:
        """Add message to chat history and persist to DB immediately"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            chat_history = session.session_metadata.get('chat_history', {})
            if not chat_history:
                raise ValueError("Chat history not initialized")
            
            timestamp = datetime.utcnow().isoformat()
            
            # Add to both message formats (for compatibility)
            message_entry = {'type': message_type, 'content': content}
            conversation_entry = {'type': message_type, 'content': content, 'timestamp': timestamp}
            
            chat_history['messages'].append(message_entry)
            chat_history['conversation_history'].append(conversation_entry)
            chat_history['total_turns'] += 1
            
            # Increment exchange count for user messages only
            if message_type == 'user':
                chat_history['exchange_count'] += 1
            
            # Save back to session
            session.session_metadata['chat_history'] = chat_history
            session.updated_at = datetime.utcnow()
            db.commit()
            
            return {
                'session_id': session.id,
                'message_added': True,
                'total_messages': len(chat_history['messages']),
                'exchange_count': chat_history['exchange_count']
            }
    
    @staticmethod
    def complete_llm_conversation(session_id: int) -> Dict[str, Any]:
        """Mark conversation complete and save final state"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            chat_history = session.session_metadata.get('chat_history', {})
            if not chat_history:
                raise ValueError("Chat history not initialized")
            
            # Mark conversation as complete
            chat_history['conversation_active'] = False
            chat_history['completed_at'] = datetime.utcnow().isoformat()
            
            # Update session status to LLM completed (if not already)
            if session.status != 'COMPLETED':
                session.complete_llm()
            else:
                # If session is already completed, ensure duration is calculated
                if session.start_time and not session.duration_seconds:
                    session.complete_session()
            
            # Save final state
            session.session_metadata['chat_history'] = chat_history
            session.updated_at = datetime.utcnow()
            db.commit()
            
            return {
                'session_id': session.id,
                'conversation_completed': True,
                'total_messages': len(chat_history['messages']),
                'total_exchanges': chat_history['exchange_count'],
                'session_status': session.status
            }
    
    @staticmethod
    def get_chat_history(session_id: int) -> Dict[str, Any]:
        """Get complete chat history for a session"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError("Session not found")
            
            chat_history = session.session_metadata.get('chat_history', {})
            
            return {
                'session_id': session.id,
                'chat_history': chat_history,
                'is_active': chat_history.get('conversation_active', False),
                'message_count': len(chat_history.get('messages', []))
            }
