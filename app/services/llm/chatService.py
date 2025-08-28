# app/services/llm/chatService.py
from typing import Optional, Generator, Dict, Any
from datetime import datetime
from ..session.assessmentOrchestrator import AssessmentOrchestrator
from ...services.sessionService import SessionService
import openai
import os
import re

class LLMChatService:
    """
    LLM Chat Service for streaming conversations
    Integrates with AssessmentOrchestrator for session-centric chat management
    """
    
    def __init__(self):
        # Initialize OpenAI client
        openai.api_key = os.getenv('OPENAI_API_KEY')
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
    
    @staticmethod
    def get_session_chat_history(session_id: int) -> Dict[str, Any]:
        """Get chat history from session metadata"""
        return AssessmentOrchestrator.get_chat_history(session_id)
    
    @staticmethod
    def stream_ai_response(session_id: int, user_message: str) -> Generator[str, None, None]:
        """
        Stream AI response using session's system prompt
        1. Add user message to session
        2. Generate AI response with streaming
        3. Yield chunks
        4. Add complete AI response to session
        """
        # Validate session
        session = SessionService.get_session(session_id)
        if not session:
            raise ValueError("Session not found")
        
        # Add user message to session history
        AssessmentOrchestrator.add_chat_message(session_id, 'user', user_message)
        
        # Get chat history for context
        chat_data = AssessmentOrchestrator.get_chat_history(session_id)
        chat_history = chat_data['chat_history']
        
        # Build conversation context for OpenAI
        messages = [
            {
                "role": "system", 
                "content": chat_history.get('system_prompt', 'You are Anisa, a helpful mental health assistant.')
            }
        ]
        
        # Add conversation history (convert format)
        for msg in chat_history.get('messages', []):
            role = 'user' if msg['type'] == 'user' else 'assistant'
            messages.append({"role": role, "content": msg['content']})
        
        try:
            # Stream response from OpenAI
            response_content = ""
            
            stream = openai.chat.completions.create(
                model="gpt-3.5-turbo",  # Use model from session settings if available
                messages=messages,
                stream=True,
                max_tokens=500,
                temperature=0.7
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    response_content += content
                    yield content
            
            # Add complete AI response to session history
            AssessmentOrchestrator.add_chat_message(session_id, 'ai', response_content)
            
        except Exception as e:
            error_msg = f"Error generating response: {str(e)}"
            # Still add the error as AI response for consistency
            AssessmentOrchestrator.add_chat_message(session_id, 'ai', error_msg)
            yield error_msg
    
    @staticmethod
    def is_conversation_complete(session_id: int) -> bool:
        """
        Check if conversation ended (detect end markers)
        Look for patterns that indicate conversation completion
        """
        chat_data = AssessmentOrchestrator.get_chat_history(session_id)
        chat_history = chat_data['chat_history']
        
        # Check if we have any messages
        messages = chat_history.get('messages', [])
        if not messages:
            return False
        
        # Get last AI message
        last_ai_messages = [msg for msg in reversed(messages) if msg['type'] == 'ai']
        if not last_ai_messages:
            return False
        
        last_ai_content = last_ai_messages[0]['content'].lower()
        
        # Look for conversation ending patterns
        end_patterns = [
            r'</end_conversation>',
            r'selesai.*percakapan',
            r'terima.*kasih.*berbagi',
            r'semoga.*bermanfaat',
            r'jaga.*kesehatan.*mental'
        ]
        
        for pattern in end_patterns:
            if re.search(pattern, last_ai_content):
                return True
        
        # Check conversation length (optional auto-end after many exchanges)
        exchange_count = chat_history.get('exchange_count', 0)
        if exchange_count >= 10:  # Auto-end after 10 user exchanges
            return True
        
        return False
    
    @staticmethod
    def start_conversation(session_id: int) -> Dict[str, Any]:
        """
        Start a new conversation with initial AI greeting
        """
        try:
            # Start conversation in orchestrator
            result = AssessmentOrchestrator.start_llm_conversation(session_id)
            
            # Generate initial AI greeting
            system_prompt = result.get('system_prompt', 'You are Anisa, a mental health assistant.')
            
            initial_greeting = "Halo! Saya Anisa, asisten kesehatan mental. Bagaimana perasaan Anda hari ini? Silakan ceritakan apa yang sedang Anda alami."
            
            # Add initial AI message
            AssessmentOrchestrator.add_chat_message(session_id, 'ai', initial_greeting)
            
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
            # Complete conversation in orchestrator
            result = AssessmentOrchestrator.complete_llm_conversation(session_id)
            
            return {
                'status': 'success',
                'conversation_completed': True,
                'total_messages': result['total_messages'],
                'total_exchanges': result['total_exchanges'],
                'completion_redirect': f'/assessment/complete/llm/{session_id}'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }