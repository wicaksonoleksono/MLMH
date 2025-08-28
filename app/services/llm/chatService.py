# app/services/llm/chatService.py
from typing import Generator, Dict, Any, List
from datetime import datetime
from ...services.sessionService import SessionService
from ...services.admin.llmService import LLMService
from ...services.assessment.llmService import LLMConversationService
from ...model.assessment.sessions import AssessmentSession
from ...db import get_session

# Langchain imports for enhanced chat management
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import ConfigurableFieldSpec
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from pydantic.v1 import BaseModel, Field


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
    
    def stream_ai_response(self, session_id: int, user_message: str) -> Generator[str, None, None]:
        """
        Stream AI response using session's system prompt from database settings
        """
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
        
        # After streaming completes, save turn to database immediately
        self._save_conversation_turn(session_id, user_message, response_content, settings)
    
    def _save_conversation_turn(self, session_id: int, user_message: str, ai_response: str, settings: Dict[str, Any]) -> None:
        """Save conversation turn immediately using LLMConversationService"""
        # Get current turn number
        existing_turns = LLMConversationService.get_session_conversations(session_id)
        turn_number = len(existing_turns) + 1
        
        # Save turn to database
        LLMConversationService.create_conversation_turn(
            session_id=session_id,
            turn_number=turn_number,
            ai_message=ai_response,
            user_message=user_message,
            ai_model_used=settings['chat_model']
        )
        
        # If conversation ended, clear LangChain memory
        if "</end_conversation>" in ai_response.lower():
            history = get_by_session_id(str(session_id))
            history.clear()
            if str(session_id) in store:
                del store[str(session_id)]
    
    @staticmethod
    def get_session_chat_history(session_id: int) -> Dict[str, Any]:
        """Get chat history using LLMConversationService"""
        conversations = LLMConversationService.get_session_conversations(session_id)
        if not conversations:
            return {"status": "error", "message": "No chat history found"}
        
        # Convert to simple format for frontend
        messages = []
        for turn in conversations:
            messages.append({"type": "ai", "content": turn.ai_message})
            messages.append({"type": "user", "content": turn.user_message})
        
        return {
            "status": "success",
            "chat_history": {
                "messages": messages,
                "total_turns": len(conversations),
                "conversation_ended": LLMConversationService.check_conversation_complete(session_id)
            }
        }
    
    @staticmethod
    def is_conversation_complete(session_id: int) -> bool:
        """Check if conversation ended using LLMConversationService"""
        return LLMConversationService.check_conversation_complete(session_id)
    
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
            
            # Clear any existing LangChain history and database turns
            history = get_by_session_id(str(session_id))
            history.clear()
            
            # Generate initial AI greeting in Indonesian
            initial_greeting = "Hai! Nama aku Anisa, temanmu yang siap mendengarkan curhatanmu. Lagi ngapain nih? Cerita dong tentang hari-harimu akhir-akhir ini!"
            
            # Add initial AI message to LangChain history
            history.add_messages([AIMessage(content=initial_greeting)])
            
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
        # Check if conversation is complete
        if LLMChatService.is_conversation_complete(session_id):
            # Get session for token
            session = SessionService.get_session(session_id)
            if not session:
                raise ValueError('Session not found')
            
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