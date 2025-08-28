# app/routes/assessment/llm_routes.py
from flask import Blueprint, request, jsonify, Response, stream_with_context
from flask_login import current_user
from ...decorators import api_response, user_required
from ...services.llm import (
    start_conversation, 
    send_message, 
    send_message_stream, 
    get_conversation_status, 
    cleanup_session,
    force_refresh_settings
)
from ...services.assessment.llmService import LLMConversationService
from ...services.sessionService import SessionService
import json
import time

llm_assessment_bp = Blueprint('llm_assessment', __name__, url_prefix='/assessment/llm')


@llm_assessment_bp.route('/start/<int:session_id>', methods=['POST'])
@user_required
@api_response
def start_conversation_route(session_id):
    """Initialize LLM conversation for a session"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or session.user_id != current_user.id:
        return {"message": "Session not found or access denied"}, 403
    
    # Start conversation
    result = start_conversation(session_id)
    return result


@llm_assessment_bp.route('/stream/<int:session_id>')
@user_required
def stream_conversation(session_id):
    """SSE endpoint for streaming LLM responses"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or session.user_id != current_user.id:
        return jsonify({"error": "Session not found or access denied"}), 403
    
    def generate():
        # Get the user message from query parameter
        user_message = request.args.get('message', '')
        
        if not user_message:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No message provided'})}\n\n"
            return
        
        # Stream the conversation
        try:
            for chunk in send_message_stream(session_id, user_message):
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


@llm_assessment_bp.route('/message/<int:session_id>', methods=['POST'])
@user_required
@api_response
def send_message_route(session_id):
    """Send user message and get AI response (non-streaming)"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or session.user_id != current_user.id:
        return {"message": "Session not found or access denied"}, 403
    
    data = request.get_json()
    user_message = data.get('message', '')
    
    if not user_message:
        return {"message": "Message is required"}, 400
    
    # Send message
    result = send_message(session_id, user_message)
    return result


@llm_assessment_bp.route('/conversations/<int:session_id>', methods=['GET'])
@user_required
@api_response
def get_session_conversations(session_id):
    """Get all conversation turns for a session"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or session.user_id != current_user.id:
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
    session = SessionService.get_session_by_id(turn.session_id)
    if not session or session.user_id != current_user.id:
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
    session = SessionService.get_session_by_id(turn.session_id)
    if not session or session.user_id != current_user.id:
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
    session = SessionService.get_session_by_id(turn.session_id)
    if not session or session.user_id != current_user.id:
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
    if not session or session.user_id != current_user.id:
        return {"message": "Session not found or access denied"}, 403
    
    # Get status from streaming service
    status = get_conversation_status(session_id)
    
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
    if not session or session.user_id != current_user.id:
        return {"message": "Session not found or access denied"}, 403
    
    result = cleanup_session(session_id)
    return result


@llm_assessment_bp.route('/refresh-settings/<int:session_id>', methods=['POST'])
@user_required
@api_response
def force_refresh_settings_route(session_id):
    """Force refresh LLM settings for a session"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or session.user_id != current_user.id:
        return {"message": "Session not found or access denied"}, 403
    
    result = force_refresh_settings(session_id)
    return result


@llm_assessment_bp.route('/check/<int:session_id>', methods=['GET'])
@user_required
@api_response
def check_conversation_complete(session_id):
    """Check if conversation has ended"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or session.user_id != current_user.id:
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
            result = start_conversation(session_id)
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
        # Send message and get response
        result = send_message(session_id, user_message)
        if result.get('status') != 'success':
            return {"message": "Failed to send message"}, 500
        
        # Check if conversation ended
        if result['data'].get('has_end_conversation'):
            # Complete LLM assessment
            SessionService.complete_llm_assessment(session_id)
            
            # Get analysis and total turns
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
        
        # Return next turn
        return {
            "conversation_ended": False,
            "next_turn": turn_number + 1,
            "ai_message": result['data']['ai_response']
        }
        
    except Exception as e:
        return {"message": str(e)}, 500