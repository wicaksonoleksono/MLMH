# app/routes/assessment/llm_routes.py
from flask import Blueprint, request, jsonify, Response, stream_with_context, render_template, redirect, url_for, flash
from flask_login import current_user, login_required
from ...decorators import api_response, user_required
# Removed deprecated service imports - using LLMChatService directly
from ...services.llm.chatService import LLMChatService
from ...services.assessment.llmService import LLMConversationService
from ...services.sessionService import SessionService
from ...services.admin.llmService import LLMService
import json
import time
from datetime import datetime
import uuid
import logging
import traceback

llm_assessment_bp = Blueprint('llm_assessment', __name__, url_prefix='/assessment/llm')


@llm_assessment_bp.route('/start/<int:session_id>', methods=['POST'])
@user_required
@api_response
def start_conversation_route(session_id):
    """Initialize LLM conversation for a session"""
    session = SessionService.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    result = LLMChatService.start_conversation(session_id)
    return result


@llm_assessment_bp.route('/send-message/<session_id>', methods=['POST'])
@user_required
@api_response
def send_message_proper(session_id):
    """POST endpoint for sending message with proper headers/auth"""
    session = SessionService.get_session(session_id)
    if not session or str(session.user_id) != str(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    data = request.get_json()
    user_message = data.get('message', '').strip()
    if not user_message:
        return {"message": "Message is required"}, 400
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
    pending_messages = getattr(send_message_proper, 'pending_messages', {})
    message_data = pending_messages.get(message_id)
    if not message_data:
        return Response("data: " + json.dumps({'type': 'error', 'message': 'Message not found'}, ensure_ascii=False) + "\n\n", 
                       mimetype='text/event-stream'), 404
    def generate():
        try:
            session_id = message_data['session_id']
            user_message = message_data['user_message']
            
            logging.info(f"🚀 Starting LLM stream for session {session_id}, message: {user_message[:50]}...")
            
            session = SessionService.get_session(session_id)
            if not session or int(session.user_id) != int(current_user.id):
                error_msg = f"Access denied for session {session_id}, user {current_user.id}"
                logging.warning(f"🚫 {error_msg}")
                yield f"data: {json.dumps({'type': 'error', 'message': 'Access denied'}, ensure_ascii=False)}\n\n"
                return
                
            chat_service = LLMChatService()
            yield f"data: {json.dumps({'type': 'stream_start'}, ensure_ascii=False)}\n\n"
            
            chunk_count = 0
            for chunk in chat_service.stream_ai_response(session_id, user_message):
                chunk_count += 1
                yield f"data: {json.dumps({'type': 'chunk', 'data': chunk}, ensure_ascii=False)}\n\n"
            
            logging.info(f"✅ Streamed {chunk_count} chunks for session {session_id}")
            
            if chat_service.is_conversation_complete(session_id):
                logging.info(f"🏁 Conversation completed for session {session_id}")
                yield f"data: {json.dumps({'type': 'complete', 'conversation_ended': True}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'complete', 'conversation_ended': False}, ensure_ascii=False)}\n\n"
                
            if message_id in pending_messages:
                del pending_messages[message_id]
                
        except Exception as e:
            # Log full error details
            error_msg = str(e)
            full_traceback = traceback.format_exc()
            logging.error(f"💥 Error for session {session_id}: {error_msg}")
            logging.error(f"Full traceback: {full_traceback}")
            
            # Send raw error to frontend - no masking
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg}, ensure_ascii=False)}\n\n"
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



@llm_assessment_bp.route('/debug/validate-config', methods=['GET'])
@user_required
@api_response
def validate_llm_config():
    """Validate LLM configuration for debugging"""
    try:
        chat_service = LLMChatService()
        settings = chat_service._load_llm_settings()
        
        return {
            "status": "success", 
            "message": "LLM configuration is valid",
            "config": {
                "has_api_key": bool(settings.get('openai_api_key_unmasked')),
                "chat_model": settings.get('chat_model'),
                "analysis_model": settings.get('analysis_model'),
                "aspects_count": len(settings.get('depression_aspects', [])),
                "analysis_scale_configured": bool(settings.get('analysis_scale'))
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "error_type": type(e).__name__
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


@llm_assessment_bp.route('/start-chat/<session_id>', methods=['POST'])
@user_required
@api_response
def start_chat(session_id):
    """Initialize LLM chat using new LangChain service"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or str(session.user_id) != str(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    try:
        result = LLMChatService.start_conversation(session.id)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@llm_assessment_bp.route('/chat-stream-new/<session_id>', methods=['POST'])
@user_required
def chat_stream_new(session_id):
    """SSE streaming endpoint for real-time chat"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return Response("data: " + json.dumps({'type': 'error', 'message': 'Session not found or access denied'}, ensure_ascii=False) + "\n\n",
                       mimetype='text/event-stream'), 403
    
    data = request.get_json()
    user_message = data.get('message', '').strip() if data else ''
    
    if not user_message:
        return Response("data: " + json.dumps({'type': 'error', 'message': 'Message is required'}, ensure_ascii=False) + "\n\n",
                       mimetype='text/event-stream'), 400

    def generate():
        try:
            # Regular message handling
            # Stream AI response
            for chunk in LLMChatService.stream_ai_response(session_id, user_message):
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
                time.sleep(0.01)  # Small delay to prevent overwhelming
            
            # Check if conversation ended
            if LLMChatService.is_conversation_complete(session_id):
                yield f"data: {json.dumps({'type': 'complete', 'conversation_ended': True}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'complete', 'conversation_ended': False}, ensure_ascii=False)}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Cache-Control'
    return response


@llm_assessment_bp.route('/finish-chat/<session_id>', methods=['POST'])
@user_required
@api_response
def finish_chat(session_id):
    """Finish conversation and prepare for completion handler"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or str(session.user_id) != str(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    try:
        result = LLMChatService.finish_conversation(session.id)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@llm_assessment_bp.route('/instructions')
@login_required  
def llm_instructions():
    """Show LLM chat assessment instructions page (standalone, no session required)"""
    try:
        # Get LLM settings for instructions
        llm_settings = LLMService.get_settings()
        
        if llm_settings and len(llm_settings) > 0:
            # Get first active setting
            settings = llm_settings[0]
            instructions = settings.get('instructions', '')
            
            # Get aspects information for display
            aspects = settings.get('depression_aspects', [])
        else:
            # Fallback if no settings configured
            instructions = "Instruksi LLM Chat belum dikonfigurasi. Silakan hubungi administrator."
            aspects = []
        
        return render_template('assessment/llm_instructions.html',
                             instructions=instructions, 
                             aspects=aspects,
                             user=current_user)
    
    except Exception as e:
        flash(f'Error loading LLM instructions: {str(e)}', 'error')
        return redirect(url_for('main.serve_index'))





