# app/services/llm/chatService.py
from typing import Generator, Dict, Any, List
from datetime import datetime
from ...services.sessionService import SessionService
from ...services.admin.llmService import LLMService
from ...model.assessment.sessions import AssessmentSession
from ...db import get_session

# Langchain imports for enhanced chat management
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import ConfigurableFieldSpec
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class InMemoryHistory(BaseChatMessageHistory, BaseModel):
    """In memory implementation of chat message history."""
    messages: List[BaseMessage] = Field(default_factory=list)

    def add_messages(self, messages: List[BaseMessage]) -> None:
        """Add a list of messages to the store"""
        self.messages.extend(messages)

    def clear(self) -> None:
        self.messages = []


# Global store for chat message history (cleared after conversation ends)
store = {}


def get_by_session_id(session_id: str) -> BaseChatMessageHistory:
    """Get chat history by session ID"""
    if session_id not in store:
        store[session_id] = InMemoryHistory()
    return store[session_id]


class LLMChatService:
    """
    LLM Chat Service for streaming conversations
    Uses proper LangChain with RunnableWithMessageHistory
    Loads system prompt and settings from database (NO fallbacks)
    """
    
    def __init__(self):
        self.chat_model = None
        self.chain_with_history = None
    
    def _load_llm_settings(self) -> Dict[str, Any]:
        """Load active LLM settings from database - NO fallbacks"""
        settings_list = LLMService.get_settings()
        if not settings_list:
            raise ValueError("No active LLM settings found. Please configure LLM settings first.")
        
        # Get first active settings
        settings = settings_list[0]
        
        # Validate required fields
        if not settings.get('openai_api_key') or not settings['openai_api_key'].strip():
            raise ValueError("OpenAI API key not configured in LLM settings")
        
        if not settings.get('chat_model') or not settings['chat_model'].strip():
            raise ValueError("Chat model not configured in LLM settings")
        
        if not settings.get('depression_aspects') or not settings['depression_aspects'].get('aspects'):
            raise ValueError("Depression aspects not configured in LLM settings")
        
        return settings
    
    def _init_langchain(self, settings: Dict[str, Any]) -> None:
        """Initialize Langchain components with settings from database"""
        try:
            # Create the chat model with settings from database
            self.chat_model = ChatOpenAI(
                model=settings['chat_model'],
                openai_api_key=settings['openai_api_key'],
                temperature=0,
                seed = 42,
                streaming=True
            )
            
            # Build system prompt from settings
            aspects = settings['depression_aspects']['aspects']
            system_prompt = LLMService.build_system_prompt(aspects)
            
            # Create prompt template with system prompt from database
            self.prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}"),
            ])
            
            # Create the chain
            self.chain = self.prompt | self.chat_model
            
            # Create chain with history management
            self.chain_with_history = RunnableWithMessageHistory(
                self.chain,
                get_by_session_id,
                input_messages_key="input",
                history_messages_key="history",
                history_factory_config=[
                    ConfigurableFieldSpec(
                        id="session_id",
                        annotation=str,
                        name="Session ID",
                        description="Unique identifier for the chat session",
                        default="",
                        is_shared=True,
                    ),
                ],
            )
        except Exception as e:
            raise ValueError(f"Failed to initialize LangChain: {str(e)}")
    
    def stream_ai_response(self, session_id: int, user_message: str) -> Generator[str, None]:
        """
        Stream AI response using session's system prompt from database settings
        """
        try:
            # Load settings from database (NO fallbacks)
            settings = self._load_llm_settings()
            
            # Initialize LangChain with database settings
            self._init_langchain(settings)
            
            # Validate session
            session = SessionService.get_session(session_id)
            if not session:
                raise ValueError("Session not found")
            
            # Stream response using Langchain
            response_content = ""
            config = {"configurable": {"session_id": str(session_id)}}
            
            for chunk in self.chain_with_history.stream(
                {"input": user_message},
                config=config
            ):
                if chunk.content:
                    content = chunk.content
                    response_content += content
                    yield content
            
            # After streaming completes, save to database if conversation ended
            if self._is_conversation_ended(response_content):
                self._save_conversation_to_database(session_id, settings)
            
        except Exception as e:
            error_msg = f"Error generating response: {str(e)}"
            yield error_msg
    
    def _is_conversation_ended(self, ai_response: str) -> bool:
        """Check if conversation ended based on AI response"""
        return "</end_conversation>" in ai_response.lower()
    
    def _save_conversation_to_database(self, session_id: int, settings: Dict[str, Any]) -> None:
        """Save complete conversation to session_metadata as JSON"""
        try:
            # Get conversation from LangChain store
            history = get_by_session_id(str(session_id))
            
            # Convert LangChain messages to simple format
            messages = []
            exchange_count = 0
            
            for msg in history.messages:
                if isinstance(msg, HumanMessage):
                    messages.append({'type': 'user', 'content': msg.content})
                    exchange_count += 1
                elif isinstance(msg, AIMessage):
                    messages.append({'type': 'ai', 'content': msg.content})
            
            # Build conversation data
            conversation_data = {
                "messages": messages,
                "exchange_count": exchange_count,
                "total_turns": len(messages),
                "system_prompt": LLMService.build_system_prompt(settings['depression_aspects']['aspects']),
                "model_used": settings['chat_model'],
                "conversation_ended": True,
                "completed_at": datetime.utcnow().isoformat()
            }
            
            # Save to database
            with get_session() as db:
                session = db.query(AssessmentSession).filter_by(id=session_id).first()
                if session:
                    if not session.session_metadata:
                        session.session_metadata = {}
                    session.session_metadata['chat_history'] = conversation_data
                    session.updated_at = datetime.utcnow()
                    db.commit()
            
            # Clear in-memory store after saving
            history.clear()
            if str(session_id) in store:
                del store[str(session_id)]
                
        except Exception as e:
            print(f"Error saving conversation to database: {e}")
    
    @staticmethod
    def get_session_chat_history(session_id: int) -> Dict[str, Any]:
        """Get chat history from session metadata"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session or not session.session_metadata:
                return {"status": "error", "message": "No chat history found"}
            
            chat_history = session.session_metadata.get('chat_history', {})
            if not chat_history:
                return {"status": "error", "message": "No chat history found"}
            
            return {
                "status": "success",
                "chat_history": chat_history
            }
    
    @staticmethod
    def is_conversation_complete(session_id: int) -> bool:
        """Check if conversation ended by checking database"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session or not session.session_metadata:
                return False
            
            chat_history = session.session_metadata.get('chat_history', {})
            return chat_history.get('conversation_ended', False)
    
    @staticmethod
    def start_conversation(session_id: int) -> Dict[str, Any]:
        """
        Start a new conversation with initial AI greeting from database settings
        """
        try:
            # Load settings to ensure they exist
            settings_list = LLMService.get_settings()
            if not settings_list:
                return {
                    'status': 'error',
                    'message': 'No LLM settings configured. Please configure settings first.'
                }
            
            # Clear any existing LangChain history
            try:
                history = get_by_session_id(str(session_id))
                history.clear()
            except Exception:
                pass
            
            # Generate initial AI greeting in Indonesian
            initial_greeting = "Hai! Nama aku Anisa, temanmu yang siap mendengarkan curhatanmu. Lagi ngapain nih? Cerita dong tentang hari-harimu akhir-akhir ini!"
            
            # Add initial AI message to LangChain history
            try:
                history = get_by_session_id(str(session_id))
                history.add_messages([AIMessage(content=initial_greeting)])
            except Exception as e:
                print(f"Warning: Could not add initial message to history: {e}")
            
            return {
                'status': 'success',
                'conversation_started': True,
                'initial_message': initial_greeting,
                'session_id': session_id
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    @staticmethod
    def finish_conversation(session_id: int) -> Dict[str, Any]:
        """
        Finish conversation and prepare for completion handler
        """
        try:
            # Check if conversation is already saved
            if LLMChatService.is_conversation_complete(session_id):
                # Get session for token
                session = SessionService.get_session(session_id)
                if not session:
                    return {'status': 'error', 'message': 'Session not found'}
                
                return {
                    'status': 'success',
                    'conversation_completed': True,
                    'completion_redirect': f'/assessment/complete/llm/{session.session_token}'
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Conversation not yet complete. Please continue chatting until Anisa ends the conversation.'
                }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }