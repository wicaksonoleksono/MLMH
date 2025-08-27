# app/services/llm/history.py
"""
LangChain chat history implementation for session-based conversations
"""

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from flask import current_app
from ...db import get_session
from ...model.assessment.sessions import AssessmentSession
from ...services.admin.llmService import LLMService as AdminLLMService


class SessionInMemoryHistory(BaseChatMessageHistory, BaseModel):
    """Session-aware chat history with dynamic system prompt management"""
    
    session_id: int = Field()
    messages: List = Field(default_factory=list)
    system_initialized: bool = Field(default=False)
    current_settings_id: Optional[int] = Field(default=None)

    def add_messages(self, messages: List) -> None:
        """Add messages to the conversation history"""
        self.messages.extend(messages)

    def clear(self) -> None:
        """Clear all messages and reset initialization state"""
        self.messages = []
        self.system_initialized = False
        self.current_settings_id = None

    def ensure_system_message(self) -> None:
        """Add or update system message based on current session's LLM settings"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=self.session_id).first()
            if not session:
                return
            
            llm_settings = session.llm_settings
            if not llm_settings:
                return
            
            # Check if settings changed
            if self.current_settings_id != llm_settings.id:
                self._update_system_message(llm_settings)
                self.current_settings_id = llm_settings.id

    def _update_system_message(self, llm_settings) -> None:
        """Update system message with current LLM settings"""
        # Build Anisa system prompt with current depression aspects
        aspects = llm_settings.depression_aspects.get('aspects', [])
        system_prompt = AdminLLMService.build_system_prompt(aspects)
        
        # Remove existing system message if present
        if self.messages and isinstance(self.messages[0], SystemMessage):
            self.messages.pop(0)
            self.system_initialized = False
        
        # Add new system message at the beginning
        self.messages.insert(0, SystemMessage(content=system_prompt))
        self.system_initialized = True

    def add_user_message(self, content: str) -> None:
        """Add a user message to the history"""
        self.add_messages([HumanMessage(content=content)])

    def add_ai_message(self, content: str) -> None:
        """Add an AI message to the history"""
        self.add_messages([AIMessage(content=content)])

    def get_messages_for_prompt(self) -> List:
        """Get messages formatted for LLM prompt (ensures system message is current)"""
        self.ensure_system_message()
        return self.messages

    def get_conversation_summary(self) -> Dict:
        """Get summary of conversation state"""
        user_messages = [msg for msg in self.messages if isinstance(msg, HumanMessage)]
        ai_messages = [msg for msg in self.messages if isinstance(msg, AIMessage)]
        
        return {
            "total_messages": len(self.messages),
            "user_messages": len(user_messages),
            "ai_messages": len(ai_messages),
            "has_system_prompt": self.system_initialized,
            "current_settings_id": self.current_settings_id
        }


# Global store for session histories - keyed by session_id
_session_store: Dict[int, SessionInMemoryHistory] = {}


def get_session_history(session_id: int) -> SessionInMemoryHistory:
    """Get or create chat history for a specific session"""
    if session_id not in _session_store:
        _session_store[session_id] = SessionInMemoryHistory(session_id=session_id)
    
    history = _session_store[session_id]
    history.ensure_system_message()
    return history


def clear_session_history(session_id: int) -> bool:
    """Clear history for a specific session"""
    if session_id in _session_store:
        _session_store[session_id].clear()
        return True
    return False


def remove_session_history(session_id: int) -> bool:
    """Remove history for a specific session (cleanup)"""
    if session_id in _session_store:
        del _session_store[session_id]
        return True
    return False


def get_all_active_sessions() -> List[int]:
    """Get list of all sessions with active history"""
    return list(_session_store.keys())


def cleanup_expired_histories(max_age_hours: int = 24) -> int:
    """Clean up histories for sessions older than max_age_hours"""
    from datetime import datetime, timedelta
    
    cleanup_count = 0
    expired_sessions = []
    
    with get_session() as db:
        for session_id in _session_store.keys():
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                # Session doesn't exist in DB anymore
                expired_sessions.append(session_id)
                continue
            
            # Check if session is too old
            age = datetime.utcnow() - session.created_at
            if age > timedelta(hours=max_age_hours):
                expired_sessions.append(session_id)
    
    # Remove expired histories
    for session_id in expired_sessions:
        remove_session_history(session_id)
        cleanup_count += 1
    
    return cleanup_count


class HistoryManager:
    """Helper class for managing session histories"""
    
    @staticmethod
    def initialize_for_session(session_id: int) -> SessionInMemoryHistory:
        """Initialize history for a new session"""
        history = get_session_history(session_id)
        history.ensure_system_message()
        return history
    
    @staticmethod
    def update_system_prompt(session_id: int) -> bool:
        """Force update system prompt for a session (when admin changes settings)"""
        if session_id in _session_store:
            history = _session_store[session_id]
            history.current_settings_id = None  # Force refresh
            history.ensure_system_message()
            return True
        return False
    
    @staticmethod
    def get_session_stats() -> Dict:
        """Get statistics about all session histories"""
        total_sessions = len(_session_store)
        total_messages = sum(len(history.messages) for history in _session_store.values())
        
        return {
            "active_sessions": total_sessions,
            "total_messages": total_messages,
            "average_messages_per_session": total_messages / total_sessions if total_sessions > 0 else 0
        }