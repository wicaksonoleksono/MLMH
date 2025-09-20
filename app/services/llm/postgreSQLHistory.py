# app/services/llm/postgreSQLHistory.py
import asyncio
from typing import List
from asgiref.sync import sync_to_async
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from app.services.assessment.llmService import LLMConversationService
from ...db import get_session

class PostgreSQLHistory(BaseChatMessageHistory):
    """PostgreSQL implementation of chat message history - zero memory usage."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id

    @property
    def messages(self) -> List[BaseMessage]:
        """Load conversation history from PostgreSQL and convert to LangChain format"""
        # Use sync_to_async to prevent blocking
        return asyncio.run(self._get_messages_async())
    
    @sync_to_async
    def _get_messages_sync(self) -> List[BaseMessage]:
        """Synchronous implementation wrapped for async"""
        try:
            # Load conversation turns from PostgreSQL
            turns = LLMConversationService.get_session_conversations(self.session_id)
            
            # Convert to LangChain message format
            langchain_messages = []
            for turn in sorted(turns, key=lambda x: x.get('turn_number', 0)):
                user_msg = turn.get('user_message', '')
                ai_msg = turn.get('ai_message', '')
                
                if user_msg:
                    langchain_messages.append(HumanMessage(content=user_msg))
                if ai_msg:
                    langchain_messages.append(AIMessage(content=ai_msg))
            
            return langchain_messages
        except Exception as e:
            # Return empty list if error (new conversation)
            print(f"Warning: Failed to load conversation history for {self.session_id}: {e}")
            return []
    
    async def _get_messages_async(self) -> List[BaseMessage]:
        """Async wrapper for message loading"""
        return await self._get_messages_sync()

    def add_messages(self, messages: List[BaseMessage]) -> None:
        """Add messages to PostgreSQL - LangChain calls this during conversation"""
        # Note: This is called by LangChain automatically during conversation flow
        # Our actual saving happens in _save_conversation_turn() method
        # This method exists to satisfy the BaseChatMessageHistory interface
        pass

    def clear(self) -> None:
        """Clear all conversation history for this session"""
        # Use sync_to_async to prevent blocking
        asyncio.run(self._clear_async())
    
    @sync_to_async
    def _clear_sync(self) -> None:
        """Synchronous implementation of clear wrapped for async"""
        try:
            # Clear conversation turns in PostgreSQL
            with get_session() as db:
                from ...model.assessment.sessions import LLMConversation
                conversation_record = db.query(LLMConversation).filter_by(session_id=self.session_id).first()
                if conversation_record:
                    conversation_record.conversation_history = {"turns": []}
                    db.commit()
        except Exception as e:
            print(f"Warning: Failed to clear conversation history for {self.session_id}: {e}")
    
    async def _clear_async(self) -> None:
        """Async wrapper for clearing history"""
        await self._clear_sync()


def get_postgresql_history_by_session_id(session_id: str) -> BaseChatMessageHistory:
    """Factory function to get PostgreSQL-based chat history by session ID"""
    return PostgreSQLHistory(session_id)