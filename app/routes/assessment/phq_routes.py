# app/routes/assessment/phq_routes.py
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import current_user, login_required
from ...decorators import api_response, user_required
from ...services.assessment.phqService import PHQResponseService
from ...services.sessionService import SessionService
from ...services.admin.phqService import PHQService

phq_assessment_bp = Blueprint('phq_assessment', __name__, url_prefix='/assessment/phq')


@phq_assessment_bp.route('/start/<session_id>', methods=['GET'])
@user_required  # TEMPORARILY COMMENTED FOR TESTING
@api_response
def get_phq_questions(session_id):
    """Get randomized PHQ questions per category for assessment - CREATE EMPTY ASSESSMENT RECORD IMMEDIATELY"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or str(session.user_id) != str(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    # GET OR CREATE PHQ ASSESSMENT RECORD with questions saved to DB
    phq_assessment_record = PHQResponseService.get_or_create_assessment_record(session_id)
    
    # DEBUG: Log what we found
    print(f"DEBUG /start: Session ID: {session_id}")
    print(f"DEBUG /start: Assessment ID: {phq_assessment_record.id}")
    print(f"DEBUG /start: Responses count: {len(phq_assessment_record.responses) if phq_assessment_record.responses else 0}")
    if phq_assessment_record.responses:
        for q_id, q_data in phq_assessment_record.responses.items():
            print(f"DEBUG /start: Question {q_id} response_value: {q_data.get('response_value')}")
    
    # Convert responses dict to questions list for frontend
    questions_list = []
    if phq_assessment_record.responses:
        # Sort by question_number to maintain order
        sorted_questions = sorted(
            phq_assessment_record.responses.values(), 
            key=lambda q: q.get('question_number', 0)
        )
        questions_list = sorted_questions
    
    # Calculate resume position based on responses that have response_value
    current_question_index = 0
    completed_responses_count = 0
    if phq_assessment_record.responses:
        # Find first question without response_value (question data exists but no answer)
        for i, question in enumerate(questions_list):
            question_id = str(question['question_id'])
            question_data = phq_assessment_record.responses.get(question_id, {})
            if question_data.get('response_value') is None:  # Properly check for None (0 is valid response)
                current_question_index = i
                break
            completed_responses_count += 1
        else:
            # All questions answered
            current_question_index = len(questions_list) - 1 if questions_list else 0
    
    return {
        "session_id": session_id,
        "assessment_id": phq_assessment_record.id,
        "questions": questions_list,
        "total_questions": len(questions_list),
        "current_question_index": current_question_index,
        "completed_responses_count": completed_responses_count,
        "resumed_from_previous": completed_responses_count > 0,
        "instructions": questions_list[0]["instructions"] if questions_list else None
    }


@phq_assessment_bp.route('/submit/<session_id>', methods=['POST'])
@user_required
@api_response
def submit_phq_responses(session_id):
    """Submit PHQ responses for a session"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or str(session.user_id) != str(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    data = request.get_json()
    responses = data.get('responses', [])
    
    if not responses:
        return {"message": "No responses provided"}, 400
    
    try:
        # Save all responses at once - no camera linking needed (assessment-first approach)
        phq_response_record = PHQResponseService.save_session_responses(
            session_id=session_id,
            responses_data=responses
        )
        
        # Prepare results for return
        results = []
        for response_data in responses:
            question_id = str(response_data['question_id'])
            if question_id in phq_response_record.responses:
                response_info = phq_response_record.responses[question_id]
                results.append({
                    "question_id": response_data['question_id'],
                    "category": response_info.get("category_name", "UNKNOWN"),
                    "score": response_info.get("response_value", 0)
                })
        
    except Exception as e:
        return {"message": f"Error processing responses: {str(e)}"}, 400
    
    # Calculate total score
    total_score = PHQResponseService.calculate_session_score(session_id)
    
    # Complete PHQ assessment and get next step directly
    completion_result = SessionService.complete_phq_and_get_next_step(session_id)
    
    return {
        "session_id": session_id,
        "responses_saved": len(results),
        "total_score": total_score,
        "response_record_id": phq_response_record.id,
        "assessment_completed": True,
        "next_redirect": completion_result["next_redirect"],
        "session_status": completion_result["session_status"],
        "message": completion_result["message"]
    }


@phq_assessment_bp.route('/responses/<session_id>', methods=['GET'])
@user_required
@api_response
def get_session_responses(session_id):
    """Get all PHQ responses for a session"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or str(session.user_id) != str(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    # Get the single PHQ response record for this session
    phq_response_record = PHQResponseService.get_session_responses(session_id)
    
    # Extract individual responses from the JSON structure
    responses_list = []
    if phq_response_record:
        for question_id, response_data in phq_response_record.responses.items():
            responses_list.append({
                "question_id": int(question_id),
                "question_number": response_data.get("question_number", 0),
                "question_text": response_data.get("question_text", ""),
                "category_name": response_data.get("category_name", ""),
                "response_value": response_data.get("response_value"),
                "response_text": response_data.get("response_text"),
                "response_time_ms": response_data.get("response_time_ms"),
                "is_completed": phq_response_record.is_completed
            })
    
    return {
        "session_id": session_id,
        "responses": responses_list,
        "total_responses": len(responses_list),
        "total_score": PHQResponseService.calculate_session_score(session_id)
    }


@phq_assessment_bp.route('/response/<session_id>/<int:question_id>', methods=['PUT'])
@user_required
@api_response
def update_phq_response(session_id, question_id):
    """Update a PHQ response for a specific question in a session"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or str(session.user_id) != str(current_user.id):
        return {"message": "Access denied"}, 403
    
    data = request.get_json()
    updates = {}
    
    # Only allow updating response value and text
    if 'response_value' in data:
        updates['response_value'] = data['response_value']
    if 'response_text' in data:
        updates['response_text'] = data['response_text']
    if 'response_time_ms' in data:
        updates['response_time_ms'] = data['response_time_ms']
    
    if not updates:
        return {"message": "No valid fields to update"}, 400
    
    try:
        print(f"DEBUG PUT: Session ID: {session_id}")
        print(f"DEBUG PUT: Updating question {question_id}, updates: {updates}")
        updated_response_record = PHQResponseService.update_response(session_id, question_id, updates)
        print(f"DEBUG PUT: Updated successfully, assessment ID: {updated_response_record.id}")
        
        # Get the specific response data from the JSON structure
        question_key = str(question_id)
        if question_key in updated_response_record.responses:
            response_data = updated_response_record.responses[question_key]
            return {
                "session_id": session_id,
                "question_id": question_id,
                "category_name": response_data.get("category_name", ""),
                "response_value": response_data.get("response_value", 0),
                "response_text": response_data.get("response_text", ""),
                "response_time_ms": response_data.get("response_time_ms"),
                "updated_at": updated_response_record.updated_at.isoformat() if hasattr(updated_response_record, 'updated_at') else None
            }
        
        return {"message": "Question response not found"}, 404
    except ValueError as e:
        return {"message": str(e)}, 404


@phq_assessment_bp.route('/score/<session_id>', methods=['GET'])
@user_required
@api_response
def get_phq_score(session_id):
    """Get PHQ score and analysis for a session"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or str(session.user_id) != str(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    total_score = PHQResponseService.calculate_session_score(session_id)
    category_scores = PHQResponseService.get_category_scores(session_id)
    max_possible_score = PHQResponseService.get_max_possible_score(session_id)
    
    return {
        "session_id": session_id,
        "total_score": total_score,
        "max_possible_score": max_possible_score,
        "category_scores": category_scores
    }


@phq_assessment_bp.route('/progress/<session_id>', methods=['GET'])
@user_required
@api_response
def get_phq_progress(session_id):
    """Get current PHQ assessment progress for resume functionality (LLM-style approach)"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or str(session.user_id) != str(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    try:
        # Get or create empty PHQ assessment record (assessment-first approach)
        phq_assessment_record = PHQResponseService.get_or_create_assessment_record(session_id)
        
        # Build questions list from assessment record
        questions_list = []
        if phq_assessment_record.responses:
            # Sort by question_number to maintain order
            sorted_questions = sorted(
                phq_assessment_record.responses.values(), 
                key=lambda q: q.get('question_number', 0)
            )
            questions_list = sorted_questions
        
        # Calculate resume position: find first question with response_value = null
        current_question_index = 0
        completed_responses_count = 0
        
        if questions_list:
            for i, question in enumerate(questions_list):
                question_id = str(question['question_id'])
                question_data = phq_assessment_record.responses.get(question_id, {})
                response_value = question_data.get('response_value')
                if response_value is None:  # First unanswered question
                    current_question_index = i
                    break
                completed_responses_count += 1
            else:
                # All questions answered
                current_question_index = len(questions_list) - 1 if questions_list else 0
        
        # Check assessment status
        is_assessment_complete = PHQResponseService.is_assessment_complete(session_id)
        expected_count = PHQResponseService.get_expected_response_count(session_id)
        
        # Assessment can start if no questions exist yet
        can_start = len(questions_list) == 0
        
        # Assessment can continue if questions exist but not all answered
        can_continue = len(questions_list) > 0 and not is_assessment_complete
        
        return {
            "session_id": session_id,
            "assessment_id": phq_assessment_record.id,
            "questions": questions_list,
            "total_questions": len(questions_list),
            "current_question_index": current_question_index,
            "completed_responses_count": completed_responses_count,
            "responses_expected": expected_count,
            "completion_percentage": (completed_responses_count / expected_count * 100) if expected_count > 0 else 0,
            "assessment_complete": is_assessment_complete,
            "can_start": can_start,
            "can_continue": can_continue,
            "resumed_from_previous": completed_responses_count > 0,
            "instructions": questions_list[0]["instructions"] if questions_list else None
        }
        
    except Exception as e:
        return {"message": f"Error getting progress: {str(e)}"}, 500


@phq_assessment_bp.route('/check/<session_id>', methods=['GET'])
@user_required
@api_response
def check_phq_completion(session_id):
    """Check if PHQ assessment is complete for session"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or str(session.user_id) != str(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    is_complete = PHQResponseService.is_assessment_complete(session_id)
    response_count = PHQResponseService.get_response_count(session_id)
    expected_count = PHQResponseService.get_expected_response_count(session_id)
    
    return {
        "session_id": session_id,
        "is_complete": is_complete,
        "responses_completed": response_count,
        "responses_expected": expected_count,
        "completion_percentage": (response_count / expected_count * 100) if expected_count > 0 else 0
    }


@phq_assessment_bp.route('/instructions')
@login_required
def phq_instructions():
    """Show PHQ assessment instructions page (standalone, no session required)"""
    try:
        # Get PHQ settings for instructions
        phq_settings = PHQService.get_settings()
        
        if phq_settings and len(phq_settings) > 0:
            # Get first active setting
            settings = phq_settings[0]
            instructions = settings.get('instructions', '')
            
            # Get scale information for display
            scale_info = settings.get('scale', {})
        else:
            # Fallback if no settings configured
            instructions = "Instruksi PHQ belum dikonfigurasi. Silakan hubungi administrator."
            scale_info = {}
        
        return render_template('assessment/phq_instructions.html', 
                             instructions=instructions,
                             scale_info=scale_info,
                             user=current_user)
    
    except Exception as e:
        flash(f'Error loading PHQ instructions: {str(e)}', 'error')
        return redirect(url_for('main.serve_index'))




