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
from langchain_openai.chat_models.base import ChatOpenAI
from typing import List


class InMemoryHistory(BaseChatMessageHistory):
    """In memory implementation of chat message history."""
    
    def __init__(self):
        self.messages: List[BaseMessage] = []

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
        
        # Validate required fields (use unmasked API key)
        if not settings.get('openai_api_key_unmasked') or not settings['openai_api_key_unmasked'].strip():
            raise ValueError("OpenAI API key not configured in LLM settings")
        
        if not settings.get('chat_model') or not settings['chat_model'].strip():
            raise ValueError("Chat model not configured in LLM settings")
        
        if not settings.get('depression_aspects') or len(settings['depression_aspects']) == 0:
            raise ValueError("Depression aspects not configured in LLM settings")
        
        return settings
    
    def _init_langchain(self, settings: Dict[str, Any]) -> None:
        """Initialize Langchain components with settings from database"""
        try:
            self.chat_model = ChatOpenAI(
                model=settings['chat_model'],
                openai_api_key=settings['openai_api_key_unmasked'],
                temperature=0,
                streaming=True
            )
            
            # Build system prompt from settings
            aspects = settings['depression_aspects']
            system_prompt = LLMService.build_system_prompt(aspects)
            
            # Create prompt template with system prompt from database
            self.prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}"),
            ])
            self.chain = self.prompt | self.chat_model
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
            # Don't hide the error - show the raw error message
            raise e
    
    def stream_ai_response(self, session_id: str, user_message: str) -> Generator[dict, None, None]:
        """
        Stream AI response using session's system prompt from database settings
        """
        try:
            settings = self._load_llm_settings()
            self._init_langchain(settings)
            session = SessionService.get_session(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            response_content = ""
            config = {"configurable": {"session_id": session_id}}
            conversation_ended = False
            
            # Stream directly without timeout/retry interference
            chunk_count = 0
            for chunk in self.chain_with_history.stream(
                {"input": user_message},
                config=config
            ):
                chunk_count += 1
                content = ""
                
                # Handle None or empty chunks properly
                if chunk is not None and hasattr(chunk, 'content') and chunk.content:
                    content = chunk.content
                # Also handle the case where chunk might be a string directly
                elif isinstance(chunk, str) and chunk:
                    content = chunk
                
                if content:
                    response_content += content
                    
                    # Check for end conversation tag in this chunk
                    content_lower = content.lower()
                    if "</end_conversation>" in content_lower or "<end_conversation>" in content_lower:
                        conversation_ended = True
                    
                    yield {
                        'content': content,
                        'conversation_ended': conversation_ended
                    }
                    
                    # If conversation ended, break the streaming loop immediately
                    if conversation_ended:
                        break
            
            if chunk_count == 0:
                raise ValueError("No response received from OpenAI")
            
            # After streaming completes, save turn to database immediately
            self._save_conversation_turn(session_id, user_message, response_content, settings)
            
        except Exception as e:
            # Show raw error - no hiding
            raise e
    
    def _save_conversation_turn(self, session_id: str, user_message: str, ai_response: str, settings: Dict[str, Any]) -> None:
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
        
        # If conversation ended, clear LangChain memory AND complete the session
        # More robust end conversation detection
        normalized_response = ai_response.lower().strip()
        if "</end_conversation>" in normalized_response or "<end_conversation>" in normalized_response or "\\u003c/end_conversation\\u003e" in normalized_response:
            history = get_by_session_id(str(session_id))
            history.clear()
            if session_id in store:
                del store[str(session_id)]
            
            # Automatically complete the LLM assessment when conversation ends
            try:
                from ...services.sessionService import SessionService
                SessionService.complete_llm_assessment(session_id)
            except Exception as e:
                # Log the error but don't fail the conversation save
                print(f"Warning: Failed to auto-complete LLM assessment for session {session_id}: {e}")
    
    @staticmethod
    def get_session_chat_history(session_id: str) -> Dict[str, Any]:
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
    def is_conversation_complete(session_id: str) -> bool:
        """Check if conversation ended using LLMConversationService"""
        return LLMConversationService.check_conversation_complete(session_id)
    
    @staticmethod
    def start_conversation(session_id: str) -> Dict[str, Any]:
        """
        Start a new conversation - prepares for initial greeting but doesn't hardcode it
        """
        try:
            settings_list = LLMService.get_settings()
            if not settings_list:
                return {
                    'status': 'error',
                    'message': 'No LLM settings configured. Please configure settings first.'
                }
            
            history = get_by_session_id(str(session_id))
            history.clear()
            
            # Return success but don't hardcode initial message
            # Let the frontend trigger the first AI response
            return {
                'status': 'success',
                'conversation_started': True,
                'session_id': session_id
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    @staticmethod
    def finish_conversation(session_id: str) -> Dict[str, Any]:
        """
        Finish conversation and prepare for completion handler
        """
        if LLMChatService.is_conversation_complete(session_id):
            # Get the LLM conversation record ID for camera linking
            conversation_record = LLMConversationService.get_conversation_by_id(session_id)
            conversation_ids = [conversation_record.id] if conversation_record else []
            
            # AUTO-LINK CAMERA CAPTURES: Link unlinked captures to LLM conversation (backend approach like PHQ)
            if conversation_record:
                from ..assessment.cameraAssessmentService import CameraAssessmentService
                try:
                    link_result = CameraAssessmentService.link_incremental_captures_to_assessment(
                        session_id=session_id,
                        assessment_id=conversation_record.id,
                        assessment_type='LLM'
                    )
                    print(f"Auto-linked LLM camera captures: {link_result}")
                except Exception as e:
                    print(f"LLM camera auto-linking failed: {e}")
            
            completion_result = SessionService.complete_llm_and_get_next_step(session_id)
            return {
                'status': 'success',
                'conversation_completed': True,
                'conversation_ids': conversation_ids,
                'next_redirect': completion_result["next_redirect"],
                'session_status': completion_result["session_status"],
                'message': completion_result["message"]
            }
        else:
            return {
                'status': 'error',
                'message': 'Conversation not yet complete. Please continue chatting until Anisa ends the conversation.'
            }