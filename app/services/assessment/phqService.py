# app/services/assessment/phqService.py
from typing import List, Dict, Any, Optional
from sqlalchemy import and_
from ...model.assessment.sessions import AssessmentSession, PHQResponse
from ...model.admin.phq import PHQQuestion, PHQSettings, PHQScale, PHQCategoryType
from ...db import get_session
from ..session.sessionTimingService import SessionTimingService
from datetime import datetime, timezone
import random


class PHQResponseService:
    """Service for handling PHQ assessment responses with CRUD operations"""

    @staticmethod
    def add_response(
        session_id: str,
        question_id: int,
        response_value: int,
        response_text: str,
        response_time_ms: Optional[int] = None
    ) -> PHQResponse:
        """Add a PHQ response to the session's response collection"""
        with get_session() as db:
            # Get session and scale for validation
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")

            # Get question details for snapshot
            question = db.query(PHQQuestion).filter_by(id=question_id).first()
            if not question:
                raise ValueError(f"PHQ question with ID {question_id} not found")

            # Get scale for dynamic validation
            phq_settings = session.phq_settings
            if not phq_settings:
                raise ValueError(f"Session {session_id} has no PHQ settings")

            scale = phq_settings.scale
            if not scale:
                raise ValueError(f"PHQ settings has no scale configured")

            # Validate response value against dynamic scale range
            if response_value < scale.min_value or response_value > scale.max_value:
                raise ValueError(f"Response value must be between {scale.min_value}-{scale.max_value}")

            # Get existing PHQ response record for this session or create new one
            phq_response_record = db.query(PHQResponse).filter_by(session_id=session_id).first()
            if not phq_response_record:
                phq_response_record = PHQResponse(
                    session_id=session_id,
                    responses={}
                )
                db.add(phq_response_record)

            # Add response to the JSON structure with clean assessment timing
            response_data = {
                "question_number": question.order_index,
                "question_text": question.question_text_id,  # Use Indonesian text
                "category_name": question.category_name_id,  # ANHEDONIA, DEPRESSED_MOOD, etc.
                "response_value": response_value,
                "response_text": response_text,
                "response_time_ms": response_time_ms,
                # Clean timing metadata will be added by frontend
            }

            # CRITICAL FIX: Force SQLAlchemy to detect JSON field change
            # We need to reassign the entire responses dict to trigger change detection
            responses_copy = dict(phq_response_record.responses)
            responses_copy[str(question_id)] = response_data
            phq_response_record.responses = responses_copy
            
            # Mark the object as modified explicitly
            from sqlalchemy.orm import attributes
            attributes.flag_modified(phq_response_record, 'responses')
            
            phq_response_record.updated_at = datetime.now(timezone.utc)

            db.commit()
            
            return phq_response_record

    @staticmethod
    def get_session_questions(session_id: str) -> List[Dict[str, Any]]:
        """Get randomized PHQ questions per category for a session"""
        with get_session() as db:
            # Get session and PHQ settings
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")

            phq_settings = session.phq_settings
            if not phq_settings:
                raise ValueError(f"Session {session_id} has no PHQ settings configured")
            questions_per_category = phq_settings.questions_per_category

            # Get all predefined categories
            categories = PHQCategoryType.get_all_categories()

            selected_questions = []
            question_number = 1

            # For each category, randomly select N questions
            for category in categories:
                # Get all active questions in this category
                category_questions = db.query(PHQQuestion).filter_by(
                    category_name_id=category['name_id'],
                    is_active=True
                ).all()

                if not category_questions:
                    print(f"Warning: No questions found for category {category['name_id']}")
                    continue  # Skip empty categories

                # Randomize questions (always true as per requirement)
                random.shuffle(category_questions)

                # Select the required number of questions per category
                selected_count = min(questions_per_category, len(category_questions))
                selected_from_category = category_questions[:selected_count]

                # Add to selected questions with metadata
                for question in selected_from_category:
                    if not question:
                        raise ValueError(f"Found None question in category {category['name_id']}")
                    if not hasattr(question, 'id') or question.id is None:
                        raise ValueError(f"Question missing ID in category {category['name_id']}: {question}")

                    selected_questions.append({
                        "question_id": question.id,
                        "question_number": question_number,
                        "question_text": question.question_text_id,
                        "question_text_en": question.question_text_en,
                        "category_name_id": category['name_id'],
                        "category_name": category['name_id'],
                        "category_display": category['name'],
                        "order_index": question.order_index
                    })
                    question_number += 1

            if not selected_questions:
                raise ValueError(f"No questions found for any category. Total categories checked: {len(categories)}")

            # Get scale information
            scale = phq_settings.scale
            if not scale:
                raise ValueError(
                    f"PHQ settings {phq_settings.id} has no scale configured (scale_id: {phq_settings.scale_id})")
            scale_labels = scale.scale_labels 
            for question in selected_questions:
                question.update({
                    "scale_min": scale.min_value if scale else 1,
                    "scale_max": scale.max_value if scale else 4,
                    "scale_labels": scale_labels,
                    "instructions": phq_settings.instructions
                })

            return selected_questions

    @staticmethod
    def _get_latest_assessment(session_id: str, db) -> PHQResponse:
        """Helper: Get latest incomplete assessment for a session"""
        # First try to get incomplete assessment
        incomplete_record = db.query(PHQResponse).filter_by(
            session_id=session_id, 
            is_completed=False
        ).order_by(PHQResponse.updated_at.desc()).first()
        
        if incomplete_record:
            return incomplete_record
            
        # If no incomplete, get the latest assessment
        return db.query(PHQResponse).filter_by(
            session_id=session_id
        ).order_by(PHQResponse.updated_at.desc()).first()

    @staticmethod
    def get_session_responses(session_id: str) -> PHQResponse:
        """Get latest incomplete PHQ assessment responses for a session"""
        with get_session() as db:
            return PHQResponseService._get_latest_assessment(session_id, db)

    @staticmethod
    def get_response_by_id(response_id: int) -> Optional[PHQResponse]:
        """Get a specific PHQ response record by ID"""
        with get_session() as db:
            return db.query(PHQResponse).filter_by(id=response_id).first()

    @staticmethod
    def update_response(session_id: str, question_id: int, updates: Dict[str, Any]) -> PHQResponse:
        """Update a PHQ response for a specific question in the session"""
        with get_session() as db:
            # Simple: Get first assessment for this session (same as LLM approach)
            phq_response_record = db.query(PHQResponse).filter_by(session_id=session_id).first()
            print(f"DEBUG SERVICE: Found assessment ID: {phq_response_record.id if phq_response_record else 'None'}")
            if not phq_response_record:
                raise ValueError(f"PHQ response record for session {session_id} not found")

            # Check if question exists in responses
            question_key = str(question_id)
            if question_key not in phq_response_record.responses:
                raise ValueError(f"Question {question_id} not found in session responses")

            # Get session and scale for validation if response_value is being updated
            if 'response_value' in updates:
                session = db.query(AssessmentSession).filter_by(id=session_id).first()
                if session and session.phq_settings and session.phq_settings.scale:
                    scale = session.phq_settings.scale
                    if updates['response_value'] < scale.min_value or updates['response_value'] > scale.max_value:
                        raise ValueError(f"Response value must be between {scale.min_value}-{scale.max_value}")
                else:
                    raise ValueError("Cannot validate response value: scale configuration not found")

            # Update the specific response
            response_data = phq_response_record.responses[question_key]
            response_data.update(updates)
            
            # Force SQLAlchemy to detect JSON field change
            responses_copy = dict(phq_response_record.responses)
            responses_copy[question_key] = response_data
            phq_response_record.responses = responses_copy
            
            # Mark the object as modified explicitly
            from sqlalchemy.orm import attributes
            attributes.flag_modified(phq_response_record, 'responses')
            
            phq_response_record.updated_at = datetime.now(timezone.utc)

            db.commit()
            
            return phq_response_record

    @staticmethod
    def delete_response(session_id: str, question_id: int) -> bool:
        """Delete a PHQ response for a specific question from the session"""
        with get_session() as db:
            phq_response_record = PHQResponseService._get_latest_assessment(session_id, db)
            if not phq_response_record:
                raise ValueError(f"PHQ response record for session {session_id} not found")

            question_key = str(question_id)
            if question_key not in phq_response_record.responses:
                raise ValueError(f"Question {question_id} not found in session responses")

            # Remove the specific response
            del phq_response_record.responses[question_key]
            phq_response_record.updated_at = datetime.now(timezone.utc)

            db.commit()
            return True

    @staticmethod
    def calculate_session_score(session_id: str) -> int:
        """Calculate total PHQ score for a session"""
        result = PHQResponseService.get_detailed_session_scores(session_id)
        return result.get("total_score", 0)

    @staticmethod
    def get_detailed_session_scores(session_id: str) -> Dict[str, Any]:
        """Calculate PHQ score for a session by category"""
        with get_session() as db:
            # Get session to access scale configuration
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                return {"total_score": 0, "category_scores": {}, "response_count": 0}

            # Get scale max value for proper scoring
            scale_max = 4  # Default fallback
            if session.phq_settings and session.phq_settings.scale:
                scale_max = session.phq_settings.scale.max_value

            # Get PHQ response record
            phq_response_record = db.query(PHQResponse).filter_by(session_id=session_id).first()
            if not phq_response_record:
                return {"total_score": 0, "category_scores": {}, "response_count": 0}

            responses = phq_response_record.responses

            if not responses:
                return {"total_score": 0, "category_scores": {}, "response_count": 0}

            # Group by category and calculate scores
            category_scores = {}
            total_score = 0

            for question_id, response_data in responses.items():
                # Extract response_value from JSON structure
                response_value = response_data.get("response_value", 0)
                
                category = response_data.get("category_name", "UNKNOWN")
                if category not in category_scores:
                    category_scores[category] = {
                        "score": 0,
                        "max_possible": 0,
                        "question_count": 0
                    }

                category_scores[category]["score"] += response_value
                category_scores[category]["max_possible"] += scale_max  # Use dynamic max value
                category_scores[category]["question_count"] += 1
                total_score += response_value

            # Calculate percentages for each category
            for category in category_scores:
                if category_scores[category]["max_possible"] > 0:
                    category_scores[category]["percentage"] = (
                        category_scores[category]["score"] / category_scores[category]["max_possible"]
                    ) * 100
                else:
                    category_scores[category]["percentage"] = 0

            max_possible_total = len(responses) * scale_max
            total_percentage = (total_score / max_possible_total) * 100 if max_possible_total > 0 else 0

            return {
                "total_score": total_score,
                "max_possible_total": max_possible_total,
                "total_percentage": total_percentage,
                "category_scores": category_scores,
                "response_count": len(responses)
            }


    @staticmethod
    def validate_session_complete(session_id: str) -> bool:
        """Check if all required PHQ questions have been answered for session"""
        with get_session() as db:
            # Get session to find PHQ settings used
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")

            # Get PHQ response record
            phq_response_record = db.query(PHQResponse).filter_by(session_id=session_id).first()
            response_count = len(phq_response_record.responses) if phq_response_record else 0

            # Get expected number of responses based on settings
            expected_count = PHQResponseService.get_expected_response_count(session_id)

            # Check if all required questions have been answered
            return response_count >= expected_count

    @staticmethod
    def get_category_scores(session_id: str) -> Dict[str, Dict[str, Any]]:
        """Get detailed category-wise scores"""
        result = PHQResponseService.get_detailed_session_scores(session_id)
        return result.get("category_scores", {})

    # Removed get_score_analysis and get_severity_level - overly verbose and unnecessary

    @staticmethod
    def is_assessment_complete(session_id: str) -> bool:
        """Check if PHQ assessment is complete for session"""
        with get_session() as db:
            phq_response_record = db.query(PHQResponse).filter_by(session_id=session_id).first()
            if not phq_response_record:
                return False

            # Check if the record is marked as completed
            return phq_response_record.is_completed

    @staticmethod
    def get_response_count(session_id: str) -> int:
        """Get number of responses completed for session"""
        with get_session() as db:
            phq_response_record = db.query(PHQResponse).filter_by(session_id=session_id).first()
            return len(phq_response_record.responses) if phq_response_record else 0

    @staticmethod
    def get_expected_response_count(session_id: str) -> int:
        """Get expected number of responses for session based on settings"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                return 0

            phq_settings = session.phq_settings
            active_categories = len(PHQCategoryType.get_all_categories())

            return active_categories * phq_settings.questions_per_category

    @staticmethod
    def get_max_possible_score(session_id: str) -> int:
        """Get maximum possible score for session"""
        with get_session() as db:
            # Get session to access scale configuration
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                return 0

            # Get scale max value for proper scoring
            scale_max = 4  # Default fallback
            if session.phq_settings and session.phq_settings.scale:
                scale_max = session.phq_settings.scale.max_value

    @staticmethod
    def clear_session_responses(session_id: str) -> int:
        """Clear all PHQ responses for a session - used for restart functionality"""
        with get_session() as db:
            phq_response_record = db.query(PHQResponse).filter_by(session_id=session_id).first()
            if phq_response_record:
                count = len(phq_response_record.responses)
                phq_response_record.responses = {}
                phq_response_record.updated_at = datetime.now(timezone.utc)
                db.commit()
                return count
            return 0

    @staticmethod
    def create_empty_assessment_record(session_id: str) -> PHQResponse:
        """Create empty PHQ assessment record immediately on assessment start (assessment-first approach)"""
        with get_session() as db:
            # Get session for validation
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")

            # Check if PHQ record already exists
            existing_record = db.query(PHQResponse).filter_by(session_id=session_id).first()
            if existing_record:
                return existing_record

            # Create empty PHQ response record
            phq_response_record = PHQResponse(
                session_id=session_id,
                responses={}  # Empty JSON, will be populated later
            )
            db.add(phq_response_record)
            db.commit()
            db.refresh(phq_response_record)
            
            return phq_response_record

    @staticmethod
    def get_or_create_assessment_record(session_id: str) -> PHQResponse:
        """Get existing PHQ assessment or create new one - SAFETY ENFORCED APPROACH"""
        with get_session() as db:
            # SAFETY: Check if assessment exists for this session_id (1 session = 1 PHQ assessment max)
            existing_records = db.query(PHQResponse).filter_by(session_id=session_id).all()
            
            # SAFETY CONSTRAINT: Enforce 1 session = 1 PHQ assessment maximum
            if len(existing_records) > 1:
                # Keep the most recent assessment, delete others
                most_recent = max(existing_records, key=lambda x: x.updated_at or x.created_at)
                for record in existing_records:
                    if record.id != most_recent.id:
                        db.delete(record)
                db.commit()
                existing_record = most_recent
            elif len(existing_records) == 1:
                existing_record = existing_records[0]
            else:
                existing_record = None
            
            if existing_record:
                # SAFETY CHECK: Validate question consistency (1 assessment = 1 question set)
                if existing_record.responses and len(existing_record.responses) > 0:
                    # Check if existing questions are from a consistent set
                    existing_question_ids = set(existing_record.responses.keys())
                    expected_question_count = PHQResponseService.get_expected_response_count(session_id)
                    
                    # SAFETY: Only clean up if there's a MAJOR inconsistency (not just minor differences)
                    if len(existing_question_ids) != expected_question_count:
                        PHQResponseService._reset_and_populate_questions(existing_record, db)
                        db.commit()
                    else:
                        # Refresh the record from DB to ensure we have latest data
                        db.refresh(existing_record)
                else:
                    # Empty assessment, populate with questions
                    PHQResponseService._populate_questions_in_responses(existing_record, db)
                    db.commit()
                    
                return existing_record

            # Create new assessment if none exists
            phq_response_record = PHQResponse(
                session_id=session_id,
                responses={}   # Will be populated with question data + responses
            )
            db.add(phq_response_record)
            db.flush()  # Get ID before populating questions
            
            # Generate questions and save them into responses JSON
            PHQResponseService._populate_questions_in_responses(phq_response_record, db)
            
            db.commit()
            db.refresh(phq_response_record)
            
            return phq_response_record

    @staticmethod
    def _reset_and_populate_questions(phq_record: PHQResponse, db) -> None:
        """SAFETY: Reset assessment and populate with clean question set"""
        # Clear existing responses to ensure clean state
        phq_record.responses = {}
        phq_record.is_completed = False
        phq_record.updated_at = datetime.now(timezone.utc)
        
        # Populate with fresh, consistent question set
        PHQResponseService._populate_questions_in_responses(phq_record, db)

    @staticmethod
    def _populate_questions_in_responses(phq_record: PHQResponse, db) -> None:
        """Generate randomized questions and save them to the PHQ record's responses JSON field"""
        # Get session and PHQ settings
        session = db.query(AssessmentSession).filter_by(id=phq_record.session_id).first()
        if not session:
            raise ValueError(f"Session {phq_record.session_id} not found")

        phq_settings = session.phq_settings
        if not phq_settings:
            raise ValueError(f"Session {phq_record.session_id} has no PHQ settings configured")
        questions_per_category = phq_settings.questions_per_category

        # Get all predefined categories
        categories = PHQCategoryType.get_all_categories()

        questions_dict = {}
        question_number = 1

        # Use session ID for consistent randomization (same session = same questions)
        session_seed = hash(phq_record.session_id) % (2**32)

        # For each category, randomly select N questions
        for category in categories:
            # Get all active questions in this category
            category_questions = db.query(PHQQuestion).filter_by(
                category_name_id=category['name_id'],
                is_active=True
            ).all()

            if not category_questions:
                continue  # Skip empty categories

            # Randomize questions with session-based seed for consistency
            category_seed = session_seed + hash(category['name_id'])  # Add category variation
            random.seed(category_seed)
            random.shuffle(category_questions)
            random.seed()  # Reset to default random state

            # Select the required number of questions per category
            selected_count = min(questions_per_category, len(category_questions))
            selected_from_category = category_questions[:selected_count]

            # Add to questions dict with metadata
            for question in selected_from_category:
                question_id = str(question.id)
                questions_dict[question_id] = {
                    "question_id": question.id,
                    "question_number": question_number,
                    "question_text": question.question_text_id,
                    "question_text_en": question.question_text_en,
                    "category_name_id": category['name_id'],
                    "category_name": category['name_id'],
                    "category_display": category['name'],
                    "order_index": question.order_index,
                    "response_value": None,
                    "response_text": None,
                    "response_time_ms": None
                }
                question_number += 1

        # Get scale information and add to all questions
        scale = phq_settings.scale
        if scale:
            scale_labels = scale.scale_labels
            for question_data in questions_dict.values():
                question_data.update({
                    "scale_min": scale.min_value,
                    "scale_max": scale.max_value,
                    "scale_labels": scale_labels,
                    "instructions": phq_settings.instructions
                })

        # Save questions to PHQ record's responses JSON (question data only, no response_value yet)
        phq_record.responses = questions_dict

    @staticmethod
    def save_session_responses(session_id: str, responses_data: List[Dict[str, Any]]) -> PHQResponse:
        """Save all PHQ responses with clean timing metadata from frontend"""
        with get_session() as db:
            # Get session and scale for validation
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")

            # Start PHQ assessment timing if not already started
            if not session.phq_start_time:
                SessionTimingService.start_phq_assessment(session_id)

            # Get scale for dynamic validation
            phq_settings = session.phq_settings
            if not phq_settings:
                raise ValueError(f"Session {session_id} has no PHQ settings")

            scale = phq_settings.scale
            if not scale:
                raise ValueError(f"PHQ settings has no scale configured")

            # Validate all responses first
            for response_data in responses_data:
                response_value = response_data['response_value']
                if response_value < scale.min_value or response_value > scale.max_value:
                    raise ValueError(f"Response value must be between {scale.min_value}-{scale.max_value}")

            # Get existing PHQ response record for this session or create new one
            phq_response_record = db.query(PHQResponse).filter_by(session_id=session_id).first()
            if not phq_response_record:
                phq_response_record = PHQResponse(
                    session_id=session_id,
                    responses={}
                )
                db.add(phq_response_record)

            # Build responses JSON structure with clean timing metadata from frontend
            responses_dict = {}
            
            for response_data in responses_data:
                question_id = response_data['question_id']
                
                # Get question details for snapshot
                question = db.query(PHQQuestion).filter_by(id=question_id).first()
                if not question:
                    raise ValueError(f"PHQ question with ID {question_id} not found")
                
                # Build response data with clean timing structure
                response_dict = {
                    "question_number": question.order_index,
                    "question_text": question.question_text_id,
                    "category_name": question.category_name_id,
                    "response_value": response_data['response_value'],
                    "response_text": response_data.get('response_text', ''),
                    "response_time_ms": response_data.get('response_time_ms')
                }
                
                # Add clean timing metadata if provided by frontend
                if 'timing' in response_data:
                    response_dict['timing'] = response_data['timing']
                
                responses_dict[str(question_id)] = response_dict

            # Update the responses JSON
            phq_response_record.responses = responses_dict
            phq_response_record.is_completed = True
            phq_response_record.updated_at = datetime.now(timezone.utc)

            db.commit()
            db.refresh(phq_response_record)

            return phq_response_record
