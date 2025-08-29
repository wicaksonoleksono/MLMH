# app/routes/assessment/phq_routes.py
from flask import Blueprint, request, jsonify
from flask_login import current_user
from ...decorators import api_response, user_required
from ...services.assessment.phqService import PHQResponseService
from ...services.sessionService import SessionService
import random

phq_assessment_bp = Blueprint('phq_assessment', __name__, url_prefix='/assessment/phq')


@phq_assessment_bp.route('/start/<session_id>', methods=['GET'])
@user_required
@api_response
def get_phq_questions(session_id):
    """Get randomized PHQ questions per category for assessment"""
    # Validate session belongs to current user
    session = SessionService.get_session(session_id)
    if not session or str(session.user_id) != str(current_user.id):
        return {"message": "Session not found or access denied"}, 403
    
    # Get randomized questions
    questions = PHQResponseService.get_session_questions(session_id)
    
    # If no questions found, try initializing assessments
    if not questions:
        from ...services.session.assessmentOrchestrator import AssessmentOrchestrator
        try:
            AssessmentOrchestrator.initialize_session_assessments(session_id)
            questions = PHQResponseService.get_session_questions(session_id)
        except Exception as e:
            return {"message": f"Failed to initialize PHQ questions: {str(e)}"}, 500
    
    return {
        "session_id": session_id,
        "questions": questions,
        "total_questions": len(questions),
        "instructions": questions[0]["instructions"] if questions else None
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
    
    # Process responses
    results = []
    for response_data in responses:
        try:
            response = PHQResponseService.create_response(
                session_id=session_id,
                question_id=response_data['question_id'],
                response_value=response_data['response_value'],
                response_text=response_data.get('response_text', ''),
                response_time_ms=response_data.get('response_time_ms')
            )
            results.append({
                "response_id": response.id,
                "question_id": response.question_id,
                "category": response.category_name,
                "score": response.response_value
            })
        except Exception as e:
            return {"message": f"Error processing response: {str(e)}"}, 400
    
    # Calculate total score
    total_score = PHQResponseService.calculate_session_score(session_id)
    
    # Complete PHQ assessment and get next step directly
    completion_result = SessionService.complete_phq_and_get_next_step(session_id)
    
    return {
        "session_id": session_id,
        "responses_saved": len(results),
        "total_score": total_score,
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
    
    responses = PHQResponseService.get_session_responses(session_id)
    
    return {
        "session_id": session_id,
        "responses": [
            {
                "id": resp.id,
                "question_id": resp.question_id,
                "question_number": resp.question_number,
                "question_text": resp.question_text,
                "category_name": resp.category_name,
                "response_value": resp.response_value,
                "response_text": resp.response_text,
                "response_time_ms": resp.response_time_ms,
                "created_at": resp.created_at.isoformat()
            }
            for resp in responses
        ],
        "total_responses": len(responses),
        "total_score": PHQResponseService.calculate_session_score(session_id)
    }


@phq_assessment_bp.route('/response/<int:response_id>', methods=['PUT'])
@user_required
@api_response
def update_phq_response(response_id):
    """Update a PHQ response"""
    response = PHQResponseService.get_response_by_id(response_id)
    if not response:
        return {"message": "Response not found"}, 404
    
    # Validate session belongs to current user
    session = SessionService.get_session(response.session_id)
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
        updated_response = PHQResponseService.update_response(response_id, updates)
        return {
            "id": updated_response.id,
            "question_id": updated_response.question_id,
            "category_name": updated_response.category_name,
            "response_value": updated_response.response_value,
            "response_text": updated_response.response_text,
            "response_time_ms": updated_response.response_time_ms,
            "updated_at": updated_response.updated_at.isoformat() if hasattr(updated_response, 'updated_at') else None
        }
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
    analysis = PHQResponseService.get_score_analysis(total_score)
    
    return {
        "session_id": session_id,
        "total_score": total_score,
        "max_possible_score": PHQResponseService.get_max_possible_score(session_id),
        "category_scores": category_scores,
        "analysis": analysis,
        "severity_level": PHQResponseService.get_severity_level(total_score)
    }


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


