# app/services/llm/streaming.py
"""
Streaming Conversation Service - Main interface for LLM streaming conversations
"""

from typing import Generator, Dict, Any, Optional, List
from datetime import datetime
from ...db import get_session
from ...model.assessment.sessions import AssessmentSession, LLMConversationTurn, LLMAnalysisResult
from .manager import GlobalSessionManager, LLMConnectionError
from ..assessment.llmService import LLMConversationService


class StreamingConversationService:
    """Service for handling streaming conversations with Anisa"""
    
    @staticmethod
    def start_conversation(session_id: int) -> Dict[str, Any]:
        """
        Initialize conversation for a session
        
        Args:
            session_id: Assessment session ID
            
        Returns:
            Dict with initialization status and first prompt
        """
        try:
            # Get or create session manager
            manager = GlobalSessionManager.get_session_manager(session_id)
            
            # Get conversation summary
            summary = manager.get_conversation_summary()
            
            # Check if conversation already started
            if summary.get("total_messages", 0) > 1:  # System message + messages
                return {
                    "status": "continued",
                    "session_id": session_id,
                    "message": "Conversation resumed",
                    "conversation_summary": summary
                }
            
            # First time - get initial Anisa greeting
            initial_prompt = "Mulai percakapan dengan sapaan yang ramah dan tanyakan bagaimana kabar hari ini."
            
            response_data = manager.get_streaming_response(initial_prompt)
            
            # Store first turn in database
            turn = LLMConversationService.create_conversation_turn(
                session_id=session_id,
                turn_number=1,
                ai_message=response_data["ai_response"],
                user_message="",  # Initial greeting has no user message
                ai_model_used=response_data.get("model_used")
            )
            
            return {
                "status": "started",
                "session_id": session_id,
                "ai_response": response_data["ai_response"],
                "turn_id": turn.id,
                "has_end_conversation": response_data["has_end_conversation"],
                "message": "Conversation started successfully"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "session_id": session_id,
                "error": str(e),
                "message": f"Failed to start conversation: {str(e)}"
            }
    
    @staticmethod
    def send_message(session_id: int, user_message: str) -> Dict[str, Any]:
        """
        Send a message and get AI response (non-streaming)
        
        Args:
            session_id: Assessment session ID
            user_message: User's message
            
        Returns:
            Dict with AI response and metadata
        """
        try:
            # Get session manager
            manager = GlobalSessionManager.get_session_manager(session_id)
            
            # Get response
            response_data = manager.get_streaming_response(user_message)
            
            # Determine turn number
            turn_number = response_data["turn_number"]
            
            # Store turn in database
            turn = LLMConversationService.create_conversation_turn(
                session_id=session_id,
                turn_number=turn_number,
                ai_message=response_data["ai_response"],
                user_message=user_message,
                ai_model_used=response_data.get("model_used")
            )
            
            # If conversation ended, trigger analysis
            analysis_result = None
            if response_data["has_end_conversation"]:
                try:
                    analysis_result = StreamingConversationService._trigger_analysis(session_id, manager)
                    
                    # Mark LLM assessment as completed
                    from ..sessionService import SessionService
                    SessionService.complete_llm_assessment(session_id)
                    
                except Exception as e:
                    print(f"Analysis failed for session {session_id}: {e}")
            
            return {
                "status": "success",
                "session_id": session_id,
                "turn_id": turn.id,
                "ai_response": response_data["ai_response"],
                "has_end_conversation": response_data["has_end_conversation"],
                "turn_number": turn_number,
                "analysis_triggered": analysis_result is not None,
                "analysis_id": analysis_result.id if analysis_result else None
            }
            
        except LLMConnectionError as e:
            return {
                "status": "llm_error",
                "session_id": session_id,
                "error": str(e),
                "message": "LLM connection error"
            }
        except Exception as e:
            return {
                "status": "error",
                "session_id": session_id,
                "error": str(e),
                "message": f"Failed to send message: {str(e)}"
            }
    
    @staticmethod
    def send_message_stream(session_id: int, user_message: str) -> Generator[Dict[str, Any], None, None]:
        """
        Send a message and stream AI response in real-time
        
        Args:
            session_id: Assessment session ID
            user_message: User's message
            
        Yields:
            Dict chunks with streaming response data
        """
        try:
            # Get session manager
            manager = GlobalSessionManager.get_session_manager(session_id)
            
            # Send initial status
            yield {
                "type": "status",
                "status": "processing",
                "session_id": session_id,
                "message": "Processing your message..."
            }
            
            # Stream response
            full_response = ""
            chunk_count = 0
            
            for chunk in manager.get_streaming_response_generator(user_message):
                full_response += chunk
                chunk_count += 1
                
                yield {
                    "type": "chunk",
                    "chunk": chunk,
                    "chunk_number": chunk_count,
                    "session_id": session_id
                }
            
            # Check for end conversation
            has_end_conversation = "</end_conversation>" in full_response.lower()
            
            # Determine turn number (approximate from history)
            summary = manager.get_conversation_summary()
            turn_number = (summary.get("total_messages", 1) - 1) // 2  # Rough estimate
            
            # Store complete turn in database
            turn = LLMConversationService.create_conversation_turn(
                session_id=session_id,
                turn_number=turn_number,
                ai_message=full_response,
                user_message=user_message,
                ai_model_used=summary.get("streaming_model")
            )
            
            # Send completion status
            yield {
                "type": "complete",
                "status": "success",
                "session_id": session_id,
                "turn_id": turn.id,
                "full_response": full_response,
                "has_end_conversation": has_end_conversation,
                "turn_number": turn_number,
                "chunk_count": chunk_count
            }
            
            # If conversation ended, trigger analysis
            if has_end_conversation:
                yield {
                    "type": "status",
                    "status": "analyzing",
                    "message": "Analyzing conversation..."
                }
                
                try:
                    analysis_result = StreamingConversationService._trigger_analysis(session_id, manager)
                    
                    # Mark LLM assessment as completed
                    from ..sessionService import SessionService
                    SessionService.complete_llm_assessment(session_id)
                    
                    yield {
                        "type": "analysis_complete",
                        "status": "success",
                        "analysis_id": analysis_result.id,
                        "total_aspects_detected": analysis_result.total_aspects_detected,
                        "average_severity": analysis_result.average_severity_score
                    }
                    
                except Exception as e:
                    yield {
                        "type": "analysis_error",
                        "status": "error",
                        "error": str(e)
                    }
            
        except LLMConnectionError as e:
            yield {
                "type": "error",
                "status": "llm_error",
                "error": str(e),
                "message": "LLM connection error"
            }
        except Exception as e:
            yield {
                "type": "error",
                "status": "error",
                "error": str(e),
                "message": f"Streaming failed: {str(e)}"
            }
    
    @staticmethod
    def _trigger_analysis(session_id: int, manager) -> LLMAnalysisResult:
        """Trigger conversation analysis using the manager's analysis agent"""
        
        # Get all conversation turns from database
        conversations = LLMConversationService.get_session_conversations(session_id)
        
        # Build conversation text
        conversation_parts = []
        for turn in conversations:
            if turn.ai_message:
                conversation_parts.append(f"Anisa: {turn.ai_message}")
            if turn.user_message:
                conversation_parts.append(f"Teman: {turn.user_message}")
        
        conversation_text = "\n\n".join(conversation_parts)
        
        # Use manager's analysis agent
        analysis_response = manager.analyze_conversation(conversation_text)
        
        # Get session settings for standardization
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            llm_settings = session.llm_settings
            aspects = llm_settings.depression_aspects.get('aspects', [])
        
        # Process and standardize results
        processed_scores = LLMConversationService._process_analysis_result(
            analysis_response["analysis_result"], 
            aspects
        )
        
        # Calculate summary stats
        total_aspects = len([score for score in processed_scores.values() if score.get('indicator_score', 0) > 0])
        avg_severity = sum(score.get('indicator_score', 0) for score in processed_scores.values()) / len(processed_scores) if processed_scores else 0
        
        # Store analysis result
        with get_session() as db:
            analysis_record = LLMAnalysisResult(
                session_id=session_id,
                analysis_model_used=analysis_response["model_used"],
                conversation_turns_analyzed=len(conversations),
                raw_analysis_result=analysis_response["analysis_result"],
                aspect_scores=processed_scores,
                total_aspects_detected=total_aspects,
                average_severity_score=avg_severity
            )
            
            db.add(analysis_record)
            db.commit()
            
            return analysis_record
    
    @staticmethod
    def get_conversation_status(session_id: int) -> Dict[str, Any]:
        """Get current conversation status for a session"""
        try:
            # Check if manager exists (conversation started)
            if session_id in GlobalSessionManager._instances:
                manager = GlobalSessionManager.get_session_manager(session_id)
                summary = manager.get_conversation_summary()
                
                # Check database for conversation completion
                with get_session() as db:
                    has_ended = db.query(LLMConversationTurn).filter_by(
                        session_id=session_id,
                        has_end_conversation=True
                    ).first() is not None
                    
                    analysis_exists = db.query(LLMAnalysisResult).filter_by(
                        session_id=session_id
                    ).first() is not None
                
                return {
                    "status": "active",
                    "session_id": session_id,
                    "conversation_started": True,
                    "conversation_ended": has_ended,
                    "analysis_completed": analysis_exists,
                    "summary": summary
                }
            else:
                return {
                    "status": "not_started",
                    "session_id": session_id,
                    "conversation_started": False,
                    "message": "Conversation not yet started"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "session_id": session_id,
                "error": str(e),
                "message": f"Failed to get conversation status: {str(e)}"
            }
    
    @staticmethod
    def cleanup_session(session_id: int) -> Dict[str, Any]:
        """Clean up session resources"""
        try:
            removed = GlobalSessionManager.remove_session_manager(session_id)
            
            return {
                "status": "success",
                "session_id": session_id,
                "cleaned_up": removed,
                "message": "Session resources cleaned up"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "session_id": session_id,
                "error": str(e),
                "message": f"Cleanup failed: {str(e)}"
            }
    
    @staticmethod
    def get_all_active_conversations() -> Dict[str, Any]:
        """Get status of all active conversations"""
        try:
            active_sessions = GlobalSessionManager.get_active_sessions()
            stats = GlobalSessionManager.get_stats()
            
            return {
                "status": "success",
                "active_conversations": active_sessions,
                "statistics": stats
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": f"Failed to get active conversations: {str(e)}"
            }
    
    @staticmethod
    def force_settings_refresh(session_id: int) -> Dict[str, Any]:
        """Force refresh LLM settings for a session (when admin updates settings)"""
        try:
            refreshed = GlobalSessionManager.force_settings_refresh(session_id)
            
            return {
                "status": "success",
                "session_id": session_id,
                "settings_refreshed": refreshed,
                "message": "LLM settings refreshed successfully"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "session_id": session_id,
                "error": str(e),
                "message": f"Settings refresh failed: {str(e)}"
            }