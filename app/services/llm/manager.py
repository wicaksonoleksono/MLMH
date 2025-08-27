# app/services/llm/manager.py
"""
Session LLM Manager for coordinating streaming conversations and analysis
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from ...db import get_session
from ...model.assessment.sessions import AssessmentSession
from .factory import LLMFactory, LLMConfigurationError, LLMConnectionError
from .history import get_session_history, remove_session_history, SessionInMemoryHistory


class SessionLLMManager:
    """Manages LLM instances and conversation history for individual sessions"""
    
    def __init__(self, session_id: int):
        self.session_id = session_id
        self.streaming_llm: Optional[ChatOpenAI] = None
        self.analysis_agent: Optional[ChatOpenAI] = None
        self.history: Optional[SessionInMemoryHistory] = None
        self.current_settings_id: Optional[int] = None
        self.last_activity: datetime = datetime.utcnow()
        self._initialized = False
    
    def ensure_initialized(self) -> bool:
        """
        Initialize or update LLM instances based on current session settings
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            with get_session() as db:
                session = db.query(AssessmentSession).filter_by(id=self.session_id).first()
                if not session:
                    raise ValueError(f"Session {self.session_id} not found")
                
                llm_settings = session.llm_settings
                if not llm_settings:
                    raise ValueError(f"No LLM settings found for session {self.session_id}")
                
                # Check if settings changed or first initialization
                if self.current_settings_id != llm_settings.id:
                    self._reinitialize_llms(llm_settings)
                    self.current_settings_id = llm_settings.id
                
                # Ensure history is initialized
                if not self.history:
                    self.history = get_session_history(self.session_id)
                
                self._initialized = True
                self.last_activity = datetime.utcnow()
                return True
                
        except Exception as e:
            print(f"Failed to initialize LLMs for session {self.session_id}: {e}")
            return False
    
    def _reinitialize_llms(self, llm_settings) -> None:
        """Reinitialize LLM instances with new settings"""
        # Validate settings first
        validation = LLMFactory.validate_settings(llm_settings)
        if not validation["valid"]:
            raise LLMConfigurationError(f"Invalid LLM settings: {', '.join(validation['issues'])}")
        
        # Create new LLM instances
        self.streaming_llm = LLMFactory.create_streaming_llm(llm_settings)
        self.analysis_agent = LLMFactory.create_analysis_agent(llm_settings)
        
        print(f"Reinitialized LLMs for session {self.session_id} with settings {llm_settings.id}")
    
    def get_streaming_response(self, user_message: str) -> Dict[str, Any]:
        """
        Get streaming response from Anisa (chat LLM)
        
        Args:
            user_message: User's input message
            
        Returns:
            Dict with response data and metadata
        """
        if not self.ensure_initialized():
            raise LLMConnectionError("Failed to initialize LLM for session")
        
        try:
            # Add user message to history
            self.history.add_user_message(user_message)
            
            # Get current conversation context
            messages = self.history.get_messages_for_prompt()
            
            # Get response from streaming LLM
            response = self.streaming_llm.invoke(messages)
            ai_response = response.content
            
            # Add AI response to history
            self.history.add_ai_message(ai_response)
            
            # Check for conversation end marker
            has_end_conversation = "</end_conversation>" in ai_response.lower()
            
            self.last_activity = datetime.utcnow()
            
            return {
                "ai_response": ai_response,
                "has_end_conversation": has_end_conversation,
                "turn_number": len([msg for msg in self.history.messages if isinstance(msg, (HumanMessage, AIMessage))]) // 2,
                "session_id": self.session_id,
                "timestamp": self.last_activity.isoformat(),
                "model_used": self.streaming_llm.model_name if hasattr(self.streaming_llm, 'model_name') else "unknown"
            }
            
        except Exception as e:
            raise LLMConnectionError(f"Failed to get streaming response: {str(e)}")
    
    def get_streaming_response_generator(self, user_message: str):
        """
        Get streaming response generator for real-time streaming
        
        Args:
            user_message: User's input message
            
        Yields:
            String chunks of the AI response
        """
        if not self.ensure_initialized():
            raise LLMConnectionError("Failed to initialize LLM for session")
        
        try:
            # Add user message to history
            self.history.add_user_message(user_message)
            
            # Get current conversation context
            messages = self.history.get_messages_for_prompt()
            
            # Stream response from LLM
            full_response = ""
            for chunk in self.streaming_llm.stream(messages):
                if chunk.content:
                    full_response += chunk.content
                    yield chunk.content
            
            # Add complete AI response to history
            self.history.add_ai_message(full_response)
            self.last_activity = datetime.utcnow()
            
        except Exception as e:
            raise LLMConnectionError(f"Failed to get streaming response: {str(e)}")
    
    def analyze_conversation(self, conversation_text: str) -> Dict[str, Any]:
        """
        Analyze conversation using analysis agent
        
        Args:
            conversation_text: Complete conversation text to analyze
            
        Returns:
            Dict with analysis results
        """
        if not self.ensure_initialized():
            raise LLMConnectionError("Failed to initialize LLM for session")
        
        try:
            with get_session() as db:
                session = db.query(AssessmentSession).filter_by(id=self.session_id).first()
                llm_settings = session.llm_settings
                
                # Build analysis prompt with current aspects
                from ...services.admin.llmService import LLMService as AdminLLMService
                aspects = llm_settings.depression_aspects.get('aspects', [])
                analysis_prompt = AdminLLMService.build_analysis_prompt(aspects)
                
                # Use analysis agent for consistent results
                messages = [
                    {"role": "system", "content": analysis_prompt},
                    {"role": "user", "content": conversation_text}
                ]
                
                response = self.analysis_agent.invoke(messages)
                
                # Try to parse as JSON
                import json
                try:
                    analysis_result = json.loads(response.content)
                except json.JSONDecodeError:
                    analysis_result = {"raw_response": response.content}
                
                return {
                    "analysis_result": analysis_result,
                    "model_used": self.analysis_agent.model_name if hasattr(self.analysis_agent, 'model_name') else "unknown",
                    "aspects_count": len(aspects),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            raise LLMConnectionError(f"Failed to analyze conversation: {str(e)}")
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get summary of current conversation state"""
        if not self.history:
            return {"error": "No conversation history"}
        
        summary = self.history.get_conversation_summary()
        summary.update({
            "session_id": self.session_id,
            "llm_initialized": self._initialized,
            "current_settings_id": self.current_settings_id,
            "last_activity": self.last_activity.isoformat(),
            "streaming_model": getattr(self.streaming_llm, 'model_name', None),
            "analysis_model": getattr(self.analysis_agent, 'model_name', None)
        })
        
        return summary
    
    def cleanup(self) -> None:
        """Clean up resources for this session"""
        remove_session_history(self.session_id)
        self.streaming_llm = None
        self.analysis_agent = None
        self.history = None
        self._initialized = False


class GlobalSessionManager:
    """Global manager for all session LLM instances"""
    
    _instances: Dict[int, SessionLLMManager] = {}
    _cleanup_threshold_hours = 24
    
    @classmethod
    def get_session_manager(cls, session_id: int) -> SessionLLMManager:
        """Get or create session manager for given session ID"""
        if session_id not in cls._instances:
            cls._instances[session_id] = SessionLLMManager(session_id)
        
        manager = cls._instances[session_id]
        manager.ensure_initialized()
        return manager
    
    @classmethod
    def remove_session_manager(cls, session_id: int) -> bool:
        """Remove and cleanup session manager"""
        if session_id in cls._instances:
            cls._instances[session_id].cleanup()
            del cls._instances[session_id]
            return True
        return False
    
    @classmethod
    def cleanup_inactive_sessions(cls, max_inactive_hours: int = None) -> int:
        """Clean up inactive session managers"""
        if max_inactive_hours is None:
            max_inactive_hours = cls._cleanup_threshold_hours
        
        cutoff_time = datetime.utcnow() - timedelta(hours=max_inactive_hours)
        inactive_sessions = []
        
        for session_id, manager in cls._instances.items():
            if manager.last_activity < cutoff_time:
                inactive_sessions.append(session_id)
        
        cleanup_count = 0
        for session_id in inactive_sessions:
            cls.remove_session_manager(session_id)
            cleanup_count += 1
        
        return cleanup_count
    
    @classmethod
    def get_active_sessions(cls) -> List[Dict[str, Any]]:
        """Get list of all active session managers"""
        return [
            {
                "session_id": session_id,
                "initialized": manager._initialized,
                "last_activity": manager.last_activity.isoformat(),
                "current_settings_id": manager.current_settings_id
            }
            for session_id, manager in cls._instances.items()
        ]
    
    @classmethod
    def force_settings_refresh(cls, session_id: int) -> bool:
        """Force refresh of LLM settings for a specific session"""
        if session_id in cls._instances:
            manager = cls._instances[session_id]
            manager.current_settings_id = None  # Force refresh
            return manager.ensure_initialized()
        return False
    
    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Get statistics about all session managers"""
        total_sessions = len(cls._instances)
        initialized_sessions = sum(1 for m in cls._instances.values() if m._initialized)
        
        return {
            "total_active_sessions": total_sessions,
            "initialized_sessions": initialized_sessions,
            "uninitialized_sessions": total_sessions - initialized_sessions,
            "cleanup_threshold_hours": cls._cleanup_threshold_hours
        }