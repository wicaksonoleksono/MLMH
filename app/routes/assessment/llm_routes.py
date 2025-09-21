# app/routes/assessment/llm_routes.py
from flask import Blueprint, request, render_template, redirect, url_for, flash, Response, stream_with_context
from flask_login import current_user, login_required
from ...decorators import api_response, user_required
# Removed deprecated service imports - using LLMChatService directly
from ...services.llm.chatService import LLMChatService
from ...services.assessment.llmService import LLMConversationService
from ...services.session.sessionManager import SessionManager
from ...services.admin.llmService import LLMService
from datetime import datetime

llm_assessment_bp = Blueprint('llm_assessment', __name__, url_prefix='/assessment/llm')

import json
import time
import logging


# Removed duplicate /start route - using /start-chat instead


@llm_assessment_bp.route('/conversation/<session_id>', methods=['GET'])
@user_required
@api_response
def get_conversation_history(session_id):
    """Get conversation history for a session"""
    # Validate session belongs to current user
    session = SessionManager.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403

    conversations = LLMConversationService.get_session_conversations(session_id)

    return {
        "session_id": session_id,
        "conversations": [
            {
                "turn_number": turn.get("turn_number"),
                "ai_message": turn.get("ai_message"),
                "user_message": turn.get("user_message"),
                "has_end_conversation": turn.get("has_end_conversation"),
                "user_message_length": turn.get("user_message_length"),
                "ai_model_used": turn.get("ai_model_used"),
                "response_audio_path": turn.get("response_audio_path"),
                "transcription": turn.get("transcription"),
                "created_at": turn.get("created_at")
            }
            for turn in conversations
        ],
        "total_turns": len(conversations)
    }


@llm_assessment_bp.route('/conversation-turn/<int:turn_id>', methods=['GET'])
@user_required
@api_response
def get_conversation_turn(turn_id):
    """Get specific conversation turn"""
    turn = LLMConversationService.get_conversation_by_id(turn_id)
    if not turn:
        return {"message": "Conversation turn not found"}, 404

    # Validate session belongs to current user
    session = SessionManager.get_session(turn.session_id)
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


@llm_assessment_bp.route('/conversation/<session_id>/<int:turn_number>', methods=['PUT'])
@user_required
@api_response
def update_conversation_turn(session_id, turn_number):
    """Update a conversation turn"""
    # Validate session belongs to current user
    session = SessionManager.get_session(session_id)
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
        updated_record = LLMConversationService.update_conversation_turn(session_id, turn_number, updates)
        
        # Extract the specific turn data from the JSON structure
        turns = updated_record.conversation_history.get("turns", [])
        updated_turn = None
        for turn in turns:
            if turn.get("turn_number") == turn_number:
                updated_turn = turn
                break
        
        if not updated_turn:
            return {"message": "Conversation turn not found"}, 404
            
        return {
            "session_id": updated_record.session_id,
            "turn_number": updated_turn.get("turn_number"),
            "ai_message": updated_turn.get("ai_message"),
            "user_message": updated_turn.get("user_message"),
            "has_end_conversation": updated_turn.get("has_end_conversation"),
            "user_message_length": updated_turn.get("user_message_length"),
            "ai_model_used": updated_turn.get("ai_model_used"),
            "response_audio_path": updated_turn.get("response_audio_path"),
            "transcription": updated_turn.get("transcription"),
            "created_at": updated_turn.get("created_at")
        }
    except ValueError as e:
        return {"message": str(e)}, 404


@llm_assessment_bp.route('/conversation/<session_id>/<int:turn_number>', methods=['DELETE'])
@user_required
@api_response
def delete_conversation_turn(session_id, turn_number):
    """Delete a conversation turn"""
    session = SessionManager.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Access denied"}, 403
    try:
        LLMConversationService.delete_conversation_turn(session_id, turn_number)
        return {"message": "Conversation turn deleted successfully"}
    except ValueError as e:
        return {"message": str(e)}, 404

@llm_assessment_bp.route('/status/<session_id>', methods=['GET'])
@user_required
@api_response
def get_conversation_status_route(session_id):
    """Get conversation status for a session"""
    session = SessionManager.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    status = {
        "conversation_complete": LLMChatService.is_conversation_complete(session_id),
        "chat_history": LLMChatService.get_session_chat_history(session_id)
    }
    summary = LLMConversationService.get_conversation_summary(session_id)
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


@llm_assessment_bp.route('/progress/<session_id>', methods=['GET'])
@user_required
@api_response
def get_llm_progress(session_id):
    """Get current LLM conversation progress for resume functionality"""
    # Validate session belongs to current user
    session = SessionManager.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    try:
        # Get or create empty conversation record
        conversation_record = LLMConversationService.create_empty_conversation_record(session_id)
        
        # Get conversation history from database conversation turns
        database_conversations = LLMConversationService.get_session_conversations(session_id)
        
        # Build unified conversation history for frontend
        conversation_messages = []
        
        # ALWAYS start with the greeting message from LangChain template
        from ...services.admin.llmService import LLMService
        greeting_message = {
            'id': 1,
            'type': 'ai', 
            'content': LLMService.GREETING,  # "Halo aku Sindi, bagaimana kabar kamu ?"
            'timestamp': None,
            'streaming': False,
            'is_greeting': True
        }
        conversation_messages.append(greeting_message)
        
        # Convert database turns to frontend format (skip if first turn is same as greeting)
        for turn in database_conversations:
            # Skip if this turn's AI message is the same as greeting (avoid duplication)
            if turn.get('ai_message') == LLMService.GREETING:
                # Add only the user message for this turn
                if turn.get('user_message'):
                    conversation_messages.append({
                        'id': len(conversation_messages) + 1,
                        'type': 'user',
                        'content': turn.get('user_message'),
                        'timestamp': turn.get('created_at'),
                        'turn_number': turn.get('turn_number')
                    })
                continue
            
            # Add user message
            if turn.get('user_message'):
                conversation_messages.append({
                    'id': len(conversation_messages) + 1,
                    'type': 'user',
                    'content': turn.get('user_message'),
                    'timestamp': turn.get('created_at'),
                    'turn_number': turn.get('turn_number')
                })
            
            # Add AI message
            conversation_messages.append({
                'id': len(conversation_messages) + 1,
                'type': 'ai',
                'content': turn.get('ai_message'),
                'timestamp': turn.get('created_at'),
                'turn_number': turn.get('turn_number')
            })
        
        # Check if conversation ended
        conversation_ended = any(turn.get("has_end_conversation", False) for turn in database_conversations)
        
        # Calculate exchange count
        exchange_count = len(database_conversations)
        
        # Determine if we can start new conversation
        can_start = not conversation_ended
        
        return {
            "session_id": session_id,
            "conversation_id": conversation_record.id,
            "conversation_messages": conversation_messages,
            "conversation_ended": conversation_ended,
            "exchange_count": exchange_count,
            "total_turns": len(database_conversations),
            "can_start": can_start,
            "greeting_message": LLMService.GREETING  # Always provide greeting for consistency
        }
        
    except Exception as e:
        return {"message": f"Error getting progress: {str(e)}"}, 500


@llm_assessment_bp.route('/cleanup/<session_id>', methods=['POST'])
@user_required
@api_response
def cleanup_session_route(session_id):
    """Cleanup session resources"""
    # Validate session belongs to current user
    session = SessionManager.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403

    # Simple cleanup - just return success since LangChain handles memory cleanup automatically
    result = {"status": "success", "message": "Session cleaned up", "session_id": session_id}
    return result


@llm_assessment_bp.route('/refresh-settings/<session_id>', methods=['POST'])
@user_required
@api_response
def force_refresh_settings_route(session_id):
    """Force refresh LLM settings for a session"""
    # Validate session belongs to current user
    session = SessionManager.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403

    # Settings are loaded fresh on each request, so just return success
    result = {"status": "success", "message": "Settings will refresh on next request", "session_id": session_id}
    return result


@llm_assessment_bp.route('/check/<session_id>', methods=['GET'])
@user_required
@api_response
def check_conversation_complete(session_id):
    """Check if conversation has ended"""
    # Validate session belongs to current user
    session = SessionManager.get_session(session_id)
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








@llm_assessment_bp.route('/save-conversation/<session_id>', methods=['POST'])
@user_required
@api_response
def save_conversation(session_id):
    """Save conversation to database (matches reference pattern)"""
    # Validate session belongs to current user
    session = SessionManager.get_session(session_id)
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




@llm_assessment_bp.route('/start-chat-async/<session_id>', methods=['POST'])
@user_required
@api_response
def start_chat_async(session_id):
    """Async version of start chat using async service methods"""
    from asgiref.sync import sync_to_async, async_to_sync
    
    # Validate session belongs to current user
    session = SessionManager.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    try:
        # CREATE EMPTY LLM CONVERSATION RECORD IMMEDIATELY (simple approach)
        conversation_record = LLMConversationService.create_empty_conversation_record(session_id)
        
        # Initialize LLM chat service (simple approach)
        result = LLMChatService.start_conversation(session.id)
        
        # Add conversation_id to result for camera to use
        if result.get("status") == "success":
            result["conversation_id"] = conversation_record.id
        
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@llm_assessment_bp.route('/start-chat/<session_id>', methods=['POST'])
@user_required
@api_response
def start_chat(session_id):
    """Initialize LLM chat - CREATE EMPTY CONVERSATION RECORD IMMEDIATELY (assessment-first approach)"""
    # Validate session belongs to current user
    session = SessionManager.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    try:
        # CREATE EMPTY LLM CONVERSATION RECORD IMMEDIATELY (assessment-first approach)
        conversation_record = LLMConversationService.create_empty_conversation_record(session_id)
        
        # Initialize LLM chat service
        result = LLMChatService.start_conversation(session.id)
        
        # Add conversation_id to result for camera to use
        if result.get("status") == "success":
            result["conversation_id"] = conversation_record.id
        
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@llm_assessment_bp.route('/chat-stream-new/<session_id>', methods=['POST'])
@user_required
def chat_stream_new(session_id):
    """SSE streaming endpoint for real-time chat"""
    # Validate session belongs to current user
    session = SessionManager.get_session(session_id)
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
            # Regular message handling using async approach
            chat_service = LLMChatService()
            
            # Use synchronous streaming (LangChain handles async internally)
            for chunk_data in chat_service.stream_ai_response(session_id, user_message):
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_data['content']}, ensure_ascii=False)}\n\n"
                time.sleep(0.01)  # Small delay to prevent overwhelming
                
                if chunk_data['conversation_ended']:
                    break
            
            # Check if conversation ended
            ended = chat_service.is_conversation_complete(session_id)
            if ended:
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
    session = SessionManager.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    try:
        result = LLMChatService.finish_conversation(session.id)
        print(f"LLM FINISH RESULT: session={session_id}, result={result}")
        return result
    except Exception as e:
        print(f"LLM FINISH ERROR: session={session_id}, error={str(e)}")
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
        # this is the fuckin problem 1. 
        return render_template('assessment/llm_instructions.html',
                             instructions=instructions, 
                             aspects=aspects,
                             user=current_user)
    
    except Exception as e:
        flash(f'Error loading LLM instructions: {str(e)}', 'error')
        return redirect(url_for('main.serve_index'))





@llm_assessment_bp.route('/save-timing/<session_id>', methods=['POST'])
@user_required
@api_response  
def save_timing_data(session_id):
    """Save timing data for user and AI messages"""
    # Validate session belongs to current user
    session = SessionManager.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Access denied"}, 403
        
    data = request.get_json()
    user_message = data.get('user_message')
    user_timing = data.get('user_timing')
    ai_timing = data.get('ai_timing')
    turn_number = data.get('turn_number')  # Use turn_number for more reliable matching
    
    if not user_message:
        return {"message": "user_message is required"}, 400
        
    # Find the most recent turn that matches this user message or turn number
    existing_turns = LLMConversationService.get_session_conversations(session_id)
    
    target_turn = None
    if turn_number is not None:
        # Use turn_number for more reliable matching
        for turn in existing_turns:
            if turn.get('turn_number') == turn_number:
                target_turn = turn
                break
    else:
        # Fallback to user_message matching for backward compatibility
        for turn in reversed(existing_turns):
            if turn.get('user_message') == user_message:
                target_turn = turn
                break
    
    if target_turn:
        # Update this turn with timing data
        updates = {}
        if user_timing:
            updates['user_timing'] = user_timing
        if ai_timing:
            updates['ai_timing'] = ai_timing
            
        print(f"DEBUG: Updating turn {target_turn.get('turn_number')} with timing: user={bool(user_timing)}, ai={bool(ai_timing)}")
        
        if updates:
            LLMConversationService.update_conversation_turn(
                session_id=session_id,
                turn_number=target_turn.get('turn_number'),
                updates=updates
            )
            print(f"DEBUG: Successfully updated turn {target_turn.get('turn_number')} with timing data")
            return {"message": "Timing data saved successfully"}
        else:
            print("DEBUG: No timing updates provided")
            return {"message": "No timing data provided"}, 400
    else:
        print(f"DEBUG: No matching turn found for user_message: '{user_message[:50]}...' or turn_number: {turn_number}")
        return {"message": f"No matching turn found for message or turn number"}, 404
    

@llm_assessment_bp.route('/stream-async/', methods=['GET'])  # New async version
def stream_sse_async():
    """Async version of SSE streaming using astream_ai_response"""
    from asgiref.sync import async_to_sync
    
    session_id = request.args.get('session_id')
    message = request.args.get('message', '').strip()
    user_token = request.args.get('user_token', '')
    user_timing_str = request.args.get('user_timing', '')
    
    def sse(event: dict):
        return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
    
    def generate():
        try:
            # Validation
            if not session_id or not message:
                yield sse({'type': 'error', 'message': 'session_id and message are required'})
                return
            
            # Auth: Try token first, then fallback to session
            auth_valid = False
            validated_user_id = None
            
            if user_token:
                token_valid, token_user_id, token_session_id = LLMService.validate_stream_token(user_token)
                if token_valid and token_session_id == session_id:
                    auth_valid = True
                    validated_user_id = token_user_id
            elif current_user.is_authenticated and (current_user.is_admin() or current_user.is_user()):
                auth_valid = True
                validated_user_id = current_user.id
            if not auth_valid:
                yield sse({'type': 'error', 'message': 'Authentication required'})
                return
            session = SessionManager.get_session(session_id)
            if not session or int(session.user_id) != int(validated_user_id):
                yield sse({'type': 'error', 'message': 'Session access denied'})
                return
            user_timing = None
            if user_timing_str:
                try:
                    user_timing = json.loads(user_timing_str)
                except:
                    user_timing = None
            
            # Stream response using ASYNC approach
            chat_service = LLMChatService()
            yield sse({'type': 'stream_start'})
            
            last_beat = time.time()
            chunk_count = 0
            
            # Use synchronous streaming (simple and works)
            for chunk_data in chat_service.stream_ai_response(session_id, message, user_timing):
                chunk_count += 1
                chunk_payload = {
                    'type': 'chunk', 
                    'data': chunk_data['content'],
                    'conversation_ended': chunk_data['conversation_ended']
                }
                yield sse(chunk_payload)
                
                # If conversation ended, stop streaming immediately
                if chunk_data['conversation_ended']:
                    break
                
                if time.time() - last_beat > 20:
                    yield ": ping\n\n"  
                    last_beat = time.time()
            time.sleep(0.1)  # 100ms should be enough for database commit
            ended = LLMChatService.is_conversation_complete(session_id)
            yield sse({'type': 'complete', 'conversation_ended': ended})
        except Exception as e:
            logging.exception("Async SSE stream error")
            yield sse({'type': 'error', 'message': str(e)})
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'X-Accel-Buffering': 'no',
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
        }
    )

@llm_assessment_bp.route('/get-stream-token/<session_id>', methods=['GET'])
@user_required
@api_response  
def get_stream_token(session_id):
    """Generate a temporary token for SSE streaming"""
    # SessionManager.get_session is already synchronous
    session = SessionManager.get_session(session_id)
    if not session or int(session.user_id) != int(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    # Token generation is fast, keep it sync
    token = LLMService.generate_stream_token(current_user.id, session_id)
    return {
        'token': token,
        'expires_in': 300,  # 5 minutes
        'session_id': session_id
    }