# app/routes/assessment/llm_routes.py
from flask import Blueprint, request, jsonify, Response, stream_with_context
from flask_login import current_user
from ...decorators import api_response, user_required
# Removed deprecated service imports - using LLMChatService directly
from ...services.llm.chatService import LLMChatService
from ...services.assessment.llmService import LLMConversationService
from ...services.sessionService import SessionService
import json
import time
from datetime import datetime

llm_assessment_bp = Blueprint('llm_assessment', __name__, url_prefix='/assessment/llm')


@llm_assessment_bp.route('/start/<int:session_id>', methods=['POST'])
@user_required
@api_response
def start_conversation_route(session_id):
    """Initialize LLM conversation for a session"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403

    # Start conversation
    result = LLMChatService.start_conversation(session_id)
    return result


@llm_assessment_bp.route('/stream/<int:session_id>')
@user_required
def stream_conversation(session_id):
    """SSE endpoint for streaming LLM responses"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return jsonify({"error": "Session not found or access denied"}), 403

    def generate():
        # Get the user message from query parameter
        user_message = request.args.get('message', '')

        if not user_message:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No message provided'})}\n\n"
            return

        # Stream the conversation
        try:
            chat_service = LLMChatService()
            for chunk in chat_service.stream_ai_response(session_id, user_message):
                yield f"data: {json.dumps(chunk)}\n\n"
                time.sleep(0.01)  # Small delay to prevent overwhelming
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Cache-Control'
        }
    )


@llm_assessment_bp.route('/send-message/<session_token>', methods=['POST'])
@user_required
@api_response
def send_message_proper(session_token):
    """POST endpoint for sending message with proper headers/auth"""
    # Get session using secure token
    session = SessionService.get_session_by_token(session_token)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    # Get message from JSON body
    data = request.get_json()
    user_message = data.get('message', '').strip()
    if not user_message:
        return {"message": "Message is required"}, 400
    
    # Generate unique message ID for this streaming session
    import uuid
    message_id = str(uuid.uuid4())
    
    # Store message temporarily for streaming (in-memory store)
    if not hasattr(send_message_proper, 'pending_messages'):
        send_message_proper.pending_messages = {}
    
    send_message_proper.pending_messages[message_id] = {
        'session_id': session.id,
        'user_message': user_message,
        'created_at': datetime.utcnow()
    }
    
    return {
        'status': 'success',
        'message_id': message_id,
        'stream_url': f'/assessment/llm/stream-response/{message_id}'
    }


@llm_assessment_bp.route('/stream-response/<message_id>')
@user_required  
def stream_response(message_id):
    """EventSource endpoint for streaming AI response to a specific message"""
    # Get pending message
    pending_messages = getattr(send_message_proper, 'pending_messages', {})
    message_data = pending_messages.get(message_id)
    
    if not message_data:
        return Response("data: " + json.dumps({'type': 'error', 'message': 'Message not found'}) + "\n\n", 
                       mimetype='text/event-stream'), 404

    def generate():
        try:
            session_id = message_data['session_id']
            user_message = message_data['user_message']
            
            # Verify session belongs to current user
            session = SessionService.get_session(session_id)
            if not session or int(session.user_id) != int(current_user.id):
                yield f"data: {json.dumps({'type': 'error', 'message': 'Access denied'})}\n\n"
                return
            
            # Initialize the chat service
            chat_service = LLMChatService()
            
            # Send stream start signal
            yield f"data: {json.dumps({'type': 'stream_start'})}\n\n"
            
            # Stream AI response using new service
            for chunk in chat_service.stream_ai_response(session_id, user_message):
                yield f"data: {json.dumps({'type': 'chunk', 'data': chunk})}\n\n"
            
            # Check if conversation ended and send completion signal
            if chat_service.is_conversation_complete(session_id):
                yield f"data: {json.dumps({'type': 'complete', 'conversation_ended': True})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'complete', 'conversation_ended': False})}\n\n"
            
            # Cleanup pending message
            if message_id in pending_messages:
                del pending_messages[message_id]

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Cache-Control'
        }
    )


@llm_assessment_bp.route('/message/<int:session_id>', methods=['POST'])
@user_required
@api_response
def send_message_route(session_id):
    """Send user message and get AI response (non-streaming)"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    data = request.get_json()
    user_message = data.get('message', '')
    if not user_message:
        return {"message": "Message is required"}, 400
    # Collect streaming response into single result
    chat_service = LLMChatService()
    full_response = ""
    for chunk in chat_service.stream_ai_response(session_id, user_message):
        full_response += chunk
    
    return {
        "status": "success", 
        "ai_response": full_response,
        "conversation_ended": LLMChatService.is_conversation_complete(session_id)
    }


@llm_assessment_bp.route('/conversations/<int:session_id>', methods=['GET'])
@user_required
@api_response
def get_session_conversations(session_id):
    """Get all conversation turns for a session"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403

    conversations = LLMConversationService.get_session_conversations(session_id)

    return {
        "session_id": session_id,
        "conversations": [
            {
                "id": turn.id,
                "turn_number": turn.turn_number,
                "ai_message": turn.ai_message,
                "user_message": turn.user_message,
                "has_end_conversation": turn.has_end_conversation,
                "user_message_length": turn.user_message_length,
                "ai_model_used": turn.ai_model_used,
                "response_audio_path": turn.response_audio_path,
                "transcription": turn.transcription,
                "created_at": turn.created_at.isoformat() if turn.created_at else None
            }
            for turn in conversations
        ]
    }


@llm_assessment_bp.route('/conversation/<int:turn_id>', methods=['GET'])
@user_required
@api_response
def get_conversation_turn(turn_id):
    """Get specific conversation turn"""
    turn = LLMConversationService.get_conversation_by_id(turn_id)
    if not turn:
        return {"message": "Conversation turn not found"}, 404

    # Validate session belongs to current user
    session = SessionService.get_session(turn.session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Access denied"}, 403

    return {
        "id": turn.id,
        "session_id": turn.session_id,
        "turn_number": turn.turn_number,
        "ai_message": turn.ai_message,
        "user_message": turn.user_message,
        "has_end_conversation": turn.has_end_conversation,
        "user_message_length": turn.user_message_length,
        "ai_model_used": turn.ai_model_used,
        "response_audio_path": turn.response_audio_path,
        "transcription": turn.transcription,
        "created_at": turn.created_at.isoformat() if turn.created_at else None
    }


@llm_assessment_bp.route('/conversation/<int:turn_id>', methods=['PUT'])
@user_required
@api_response
def update_conversation_turn(turn_id):
    """Update a conversation turn"""
    turn = LLMConversationService.get_conversation_by_id(turn_id)
    if not turn:
        return {"message": "Conversation turn not found"}, 404

    # Validate session belongs to current user
    session = SessionService.get_session(turn.session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Access denied"}, 403

    data = request.get_json()
    updates = {}

    # Only allow updating specific fields
    allowed_fields = ['ai_message', 'user_message', 'response_audio_path', 'transcription']
    for field in allowed_fields:
        if field in data:
            updates[field] = data[field]

    if not updates:
        return {"message": "No valid fields to update"}, 400

    try:
        updated_turn = LLMConversationService.update_conversation_turn(turn_id, updates)
        return {
            "id": updated_turn.id,
            "session_id": updated_turn.session_id,
            "turn_number": updated_turn.turn_number,
            "ai_message": updated_turn.ai_message,
            "user_message": updated_turn.user_message,
            "has_end_conversation": updated_turn.has_end_conversation,
            "user_message_length": updated_turn.user_message_length,
            "ai_model_used": updated_turn.ai_model_used,
            "response_audio_path": updated_turn.response_audio_path,
            "transcription": updated_turn.transcription,
            "created_at": updated_turn.created_at.isoformat() if updated_turn.created_at else None
        }
    except ValueError as e:
        return {"message": str(e)}, 404


@llm_assessment_bp.route('/conversation/<int:turn_id>', methods=['DELETE'])
@user_required
@api_response
def delete_conversation_turn(turn_id):
    """Delete a conversation turn"""
    turn = LLMConversationService.get_conversation_by_id(turn_id)
    if not turn:
        return {"message": "Conversation turn not found"}, 404

    # Validate session belongs to current user
    session = SessionService.get_session(turn.session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Access denied"}, 403

    try:
        LLMConversationService.delete_conversation_turn(turn_id)
        return {"message": "Conversation turn deleted successfully"}
    except ValueError as e:
        return {"message": str(e)}, 404


@llm_assessment_bp.route('/status/<int:session_id>', methods=['GET'])
@user_required
@api_response
def get_conversation_status_route(session_id):
    """Get conversation status for a session"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403

    # Get status from chat service and conversation service
    status = {
        "conversation_complete": LLMChatService.is_conversation_complete(session_id),
        "chat_history": LLMChatService.get_session_chat_history(session_id)
    }

    # Get conversation summary from assessment service
    summary = LLMConversationService.get_conversation_summary(session_id)

    # Get analysis result if available
    analysis = LLMConversationService.get_session_analysis(session_id)

    return {
        "session_id": session_id,
        "streaming_status": status,
        "conversation_summary": summary,
        "analysis_result": {
            "id": analysis.id,
            "analysis_model_used": analysis.analysis_model_used,
            "conversation_turns_analyzed": analysis.conversation_turns_analyzed,
            "aspect_scores": analysis.aspect_scores,
            "total_aspects_detected": analysis.total_aspects_detected,
            "average_severity_score": analysis.average_severity_score,
            "created_at": analysis.created_at.isoformat()
        } if analysis else None
    }


@llm_assessment_bp.route('/cleanup/<int:session_id>', methods=['POST'])
@user_required
@api_response
def cleanup_session_route(session_id):
    """Cleanup session resources"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403

    # Simple cleanup - just return success since LangChain handles memory cleanup automatically
    result = {"status": "success", "message": "Session cleaned up", "session_id": session_id}
    return result


@llm_assessment_bp.route('/refresh-settings/<int:session_id>', methods=['POST'])
@user_required
@api_response
def force_refresh_settings_route(session_id):
    """Force refresh LLM settings for a session"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403

    # Settings are loaded fresh on each request, so just return success
    result = {"status": "success", "message": "Settings will refresh on next request", "session_id": session_id}
    return result


@llm_assessment_bp.route('/check/<int:session_id>', methods=['GET'])
@user_required
@api_response
def check_conversation_complete(session_id):
    """Check if conversation has ended"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403

    is_complete = LLMConversationService.check_conversation_complete(session_id)
    analysis = LLMConversationService.get_session_analysis(session_id)

    return {
        "session_id": session_id,
        "conversation_complete": is_complete,
        "analysis_available": analysis is not None,
        "analysis_id": analysis.id if analysis else None
    }


@llm_assessment_bp.route('/current-turn/<int:session_id>', methods=['GET'])
@user_required
@api_response
def get_current_turn(session_id):
    """Get current conversation turn for simple UI flow"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or session.user_id != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403

    try:
        # Check if conversation is complete
        is_complete = LLMConversationService.check_conversation_complete(session_id)
        if is_complete:
            analysis = LLMConversationService.get_session_analysis(session_id)
            total_turns = LLMConversationService.get_total_turns(session_id)
            return {
                "conversation_ended": True,
                "total_turns": total_turns,
                "analysis": {
                    "total_aspects_detected": analysis.total_aspects_detected if analysis else 0,
                    "average_severity": analysis.average_severity_score if analysis else 0.0
                } if analysis else None
            }

        # Get current turn or start new conversation
        current_turn_data = LLMConversationService.get_current_turn_for_session(session_id)
        if not current_turn_data:
            # Start new conversation
            result = LLMChatService.start_conversation(session_id)
            if result.get('status') != 'success':
                return {"message": "Failed to start conversation"}, 500

            return {
                "conversation_ended": False,
                "turn_number": 1,
                "ai_message": result['data']['ai_response']
            }

        return {
            "conversation_ended": False,
            "turn_number": current_turn_data['turn_number'],
            "ai_message": current_turn_data['ai_message']
        }

    except Exception as e:
        return {"message": str(e)}, 500


@llm_assessment_bp.route('/submit-turn/<int:session_id>', methods=['POST'])
@user_required
@api_response
def submit_turn(session_id):
    """Submit user response and get next turn"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or session.user_id != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403

    data = request.get_json()
    turn_number = data.get('turn_number')
    user_message = data.get('user_message', '').strip()

    if not user_message:
        return {"message": "User message is required"}, 400

    try:
        # Send message and get response via streaming
        chat_service = LLMChatService()
        full_response = ""
        for chunk in chat_service.stream_ai_response(session_id, user_message):
            full_response += chunk
        
        result = {
            "status": "success",
            "ai_response": full_response,
            "conversation_ended": LLMChatService.is_conversation_complete(session_id)
        }
        if result.get('status') != 'success':
            return {"message": "Failed to send message"}, 500

        # Check if conversation ended
        if result['data'].get('has_end_conversation'):
            # Get analysis and total turns for reference
            analysis = LLMConversationService.get_session_analysis(session_id)
            total_turns = LLMConversationService.get_total_turns(session_id)
            
            # Complete LLM assessment and get next step directly
            from ...services.sessionService import SessionService
            completion_result = SessionService.complete_llm_and_get_next_step(session_id)

            return {
                "conversation_ended": True,
                "total_turns": total_turns,
                "analysis": {
                    "total_aspects_detected": analysis.total_aspects_detected if analysis else 0,
                    "average_severity": analysis.average_severity_score if analysis else 0.0
                } if analysis else None,
                "next_redirect": completion_result["next_redirect"],
                "session_status": completion_result["session_status"],
                "message": completion_result["message"]
            }

        # Return next turn
        return {
            "conversation_ended": False,
            "next_turn": turn_number + 1,
            "ai_message": result['data']['ai_response']
        }

    except Exception as e:
        return {"message": str(e)}, 500


@llm_assessment_bp.route('/save-conversation/<int:session_id>', methods=['POST'])
@user_required
@api_response
def save_conversation(session_id):
    """Save conversation to database (matches reference pattern)"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403

    try:
        # The conversation is already being saved automatically via the history persistence
        # This endpoint confirms the save and returns status

        # Get conversation summary
        summary = LLMConversationService.get_conversation_summary(session_id)

        # Check if conversation is complete
        is_complete = LLMConversationService.check_conversation_complete(session_id)

        # Get analysis if available
        analysis = LLMConversationService.get_session_analysis(session_id)

        return {
            "status": "success",
            "session_id": session_id,
            "conversation_saved": True,
            "conversation_complete": is_complete,
            "total_turns": summary.get('total_turns', 0),
            "analysis_available": analysis is not None,
            "message": "Conversation saved successfully"
        }

    except Exception as e:
        return {
            "status": "error",
            "session_id": session_id,
            "error": str(e),
            "message": f"Failed to save conversation: {str(e)}"
        }, 500


@llm_assessment_bp.route('/debug-session/<int:session_id>', methods=['GET'])
@user_required
@api_response
def debug_session_status(session_id):
    """Debug endpoint to check session status"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403

    return {
        "session_id": session.id,
        "status": session.status,
        "is_first": session.is_first,
        "consent_completed": session.consent_completed_at is not None,
        "camera_completed": session.camera_completed,
        "phq_completed": session.phq_completed_at is not None,
        "llm_completed": session.llm_completed_at is not None,
        "next_assessment_type": session.next_assessment_type,
        "can_start_assessment": session.can_start_assessment,
        "session_metadata_keys": list(session.session_metadata.keys()) if session.session_metadata else [],
        "assessment_order": session.assessment_order
    }


# ============================================================================
# NEW SSE STREAMING ENDPOINTS (AssessmentOrchestrator Integration)
# ============================================================================

@llm_assessment_bp.route('/start-chat/<session_token>', methods=['POST'])
@user_required
@api_response
def start_chat(session_token):
    """Initialize LLM chat using new LangChain service"""
    # Validate session belongs to current user
    session = SessionService.get_session_by_token(session_token)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    try:
        result = LLMChatService.start_conversation(session.id)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@llm_assessment_bp.route('/chat-stream-new/<int:session_id>', methods=['POST'])
@user_required
def chat_stream_new(session_id):
    """SSE streaming endpoint for real-time chat"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return Response("data: " + json.dumps({'type': 'error', 'message': 'Session not found or access denied'}) + "\n\n",
                       mimetype='text/event-stream'), 403
    
    data = request.get_json()
    user_message = data.get('message', '').strip() if data else ''
    
    if not user_message:
        return Response("data: " + json.dumps({'type': 'error', 'message': 'Message is required'}) + "\n\n",
                       mimetype='text/event-stream'), 400

    def generate():
        try:
            # Stream AI response
            for chunk in LLMChatService.stream_ai_response(session_id, user_message):
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                time.sleep(0.01)  # Small delay to prevent overwhelming
            
            # Check if conversation ended
            if LLMChatService.is_conversation_complete(session_id):
                yield f"data: {json.dumps({'type': 'complete', 'conversation_ended': True})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'complete', 'conversation_ended': False})}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Cache-Control'
    return response


@llm_assessment_bp.route('/finish-chat/<session_token>', methods=['POST'])
@user_required
@api_response
def finish_chat(session_token):
    """Finish conversation and prepare for completion handler"""
    # Validate session belongs to current user
    session = SessionService.get_session_by_token(session_token)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    try:
        result = LLMChatService.finish_conversation(session.id)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@llm_assessment_bp.route('/chat-history/<int:session_id>', methods=['GET'])
@user_required
@api_response  
def get_chat_history(session_id):
    """Get chat history for session"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    try:
        result = LLMChatService.get_session_chat_history(session_id)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500
