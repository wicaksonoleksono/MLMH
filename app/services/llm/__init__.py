# app/services/llm/__init__.py

# Convenience functions for quick access
def start_conversation(session_id: int):
    from .streaming import StreamingConversationService
    return StreamingConversationService.start_conversation(session_id)

def send_message(session_id: int, user_message: str):
    from .streaming import StreamingConversationService
    return StreamingConversationService.send_message(session_id, user_message)

def send_message_stream(session_id: int, user_message: str):
    from .streaming import StreamingConversationService
    return StreamingConversationService.send_message_stream(session_id, user_message)

def get_conversation_status(session_id: int):
    from .streaming import StreamingConversationService
    return StreamingConversationService.get_conversation_status(session_id)

def cleanup_session(session_id: int):
    from .streaming import StreamingConversationService
    return StreamingConversationService.cleanup_session(session_id)

def force_refresh_settings(session_id: int):
    from .streaming import StreamingConversationService
    return StreamingConversationService.force_settings_refresh(session_id)