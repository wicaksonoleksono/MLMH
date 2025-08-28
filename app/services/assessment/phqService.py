# app/services/assessment/phqService.py
from typing import List, Dict, Any, Optional
from sqlalchemy import and_
from ...model.assessment.sessions import AssessmentSession, PHQResponse
from ...model.admin.phq import PHQQuestion, PHQSettings, PHQScale, PHQCategoryType
from ...db import get_session
from datetime import datetime
import random


class PHQResponseService:
    """Service for handling PHQ assessment responses with CRUD operations"""

    @staticmethod
    def create_response(
        session_id: int,
        question_id: int,
        response_value: int,
        response_text: str,
        response_time_ms: Optional[int] = None
    ) -> PHQResponse:
        """Create a PHQ response for a session"""
        with get_session() as db:
            # Get question details for snapshot
            question = db.query(PHQQuestion).filter_by(id=question_id).first()
            if not question:
                raise ValueError(f"PHQ question with ID {question_id} not found")

            # Validate response value (should be 0-3)
            if response_value not in [0, 1, 2, 3]:
                raise ValueError("Response value must be between 0-3")

            response = PHQResponse(
                session_id=session_id,
                question_id=question_id,
                question_number=question.order_index,
                question_text=question.question_text_id,  # Use Indonesian text
                category_name=question.category_name_id,  # ANHEDONIA, DEPRESSED_MOOD, etc.
                response_value=response_value,
                response_text=response_text,
                response_time_ms=response_time_ms
            )

            db.add(response)
            db.commit()
            return response

    @staticmethod
    def get_session_questions(session_id: int) -> List[Dict[str, Any]]:
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
                raise ValueError(f"PHQ settings {phq_settings.id} has no scale configured (scale_id: {phq_settings.scale_id})")
            
            scale_labels = scale.scale_labels if scale else {
                0: "Tidak sama sekali",
                1: "Beberapa hari",
                2: "Lebih dari setengah hari",
                3: "Hampir setiap hari"
            }

            # Add metadata to response
            for question in selected_questions:
                question.update({
                    "scale_min": scale.min_value if scale else 0,
                    "scale_max": scale.max_value if scale else 3,
                    "scale_labels": scale_labels,
                    "instructions": phq_settings.instructions
                })

            return selected_questions

    @staticmethod
    def get_session_responses(session_id: int) -> List[PHQResponse]:
        """Get all PHQ responses for a session"""
        with get_session() as db:
            return db.query(PHQResponse).filter_by(session_id=session_id).order_by(PHQResponse.question_number).all()

    @staticmethod
    def get_response_by_id(response_id: int) -> Optional[PHQResponse]:
        """Get a specific PHQ response by ID"""
        with get_session() as db:
            return db.query(PHQResponse).filter_by(id=response_id).first()

    @staticmethod
    def update_response(response_id: int, updates: Dict[str, Any]) -> PHQResponse:
        """Update a PHQ response"""
        with get_session() as db:
            response = db.query(PHQResponse).filter_by(id=response_id).first()
            if not response:
                raise ValueError(f"PHQ response with ID {response_id} not found")

            # Validate response_value if being updated
            if 'response_value' in updates and updates['response_value'] not in [0, 1, 2, 3]:
                raise ValueError("Response value must be between 0-3")

            for key, value in updates.items():
                if hasattr(response, key):
                    setattr(response, key, value)

            db.commit()
            return response

    @staticmethod
    def delete_response(response_id: int) -> bool:
        """Delete a PHQ response"""
        with get_session() as db:
            response = db.query(PHQResponse).filter_by(id=response_id).first()
            if not response:
                raise ValueError(f"PHQ response with ID {response_id} not found")

            db.delete(response)
            db.commit()
            return True

    @staticmethod
    def calculate_session_score(session_id: int) -> int:
        """Calculate total PHQ score for a session"""
        result = PHQResponseService.get_detailed_session_scores(session_id)
        return result.get("total_score", 0)

    @staticmethod
    def get_detailed_session_scores(session_id: int) -> Dict[str, Any]:
        """Calculate PHQ score for a session by category"""
        with get_session() as db:
            responses = db.query(PHQResponse).filter_by(session_id=session_id).all()

            if not responses:
                return {"total_score": 0, "category_scores": {}, "response_count": 0}

            # Group by category and calculate scores
            category_scores = {}
            total_score = 0

            for response in responses:
                category = response.category_name
                if category not in category_scores:
                    category_scores[category] = {
                        "score": 0,
                        "max_possible": 0,
                        "question_count": 0
                    }

                category_scores[category]["score"] += response.response_value
                category_scores[category]["max_possible"] += 3  # Max value per question
                category_scores[category]["question_count"] += 1
                total_score += response.response_value

            # Calculate percentages for each category
            for category in category_scores:
                if category_scores[category]["max_possible"] > 0:
                    category_scores[category]["percentage"] = (
                        category_scores[category]["score"] / category_scores[category]["max_possible"]
                    ) * 100
                else:
                    category_scores[category]["percentage"] = 0

            max_possible_total = len(responses) * 3
            total_percentage = (total_score / max_possible_total) * 100 if max_possible_total > 0 else 0

            return {
                "total_score": total_score,
                "max_possible_total": max_possible_total,
                "total_percentage": total_percentage,
                "category_scores": category_scores,
                "response_count": len(responses)
            }

    @staticmethod
    def bulk_create_responses(session_id: int, responses_data: List[Dict[str, Any]]) -> List[PHQResponse]:
        """Create multiple PHQ responses at once"""
        created_responses = []

        for response_data in responses_data:
            response = PHQResponseService.create_response(
                session_id=session_id,
                question_id=response_data['question_id'],
                response_value=response_data['response_value'],
                response_text=response_data['response_text'],
                response_time_ms=response_data.get('response_time_ms')
            )
            created_responses.append(response)

        return created_responses

    @staticmethod
    def validate_session_complete(session_id: int) -> bool:
        """Check if all required PHQ questions have been answered for session"""
        with get_session() as db:
            # Get session to find PHQ settings used
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")

            # Get PHQ settings to determine required questions
            phq_settings = session.phq_settings

            # Get all responses for this session
            responses = db.query(PHQResponse).filter_by(session_id=session_id).all()
            response_question_ids = {r.question_id for r in responses}

            # Get required questions based on settings
            # This would depend on how PHQ settings determine which questions to ask
            # For now, assume all active questions
            required_questions = db.query(PHQQuestion).filter(
                PHQQuestion.is_active == True
            ).all()

            required_question_ids = {q.id for q in required_questions}

            # Check if all required questions have been answered
            return required_question_ids.issubset(response_question_ids)

    @staticmethod
    def get_category_scores(session_id: int) -> Dict[str, Dict[str, Any]]:
        """Get detailed category-wise scores"""
        result = PHQResponseService.get_detailed_session_scores(session_id)
        return result.get("category_scores", {})

    @staticmethod
    def get_score_analysis(total_score: int) -> Dict[str, Any]:
        """Get PHQ score analysis and interpretation"""
        if total_score <= 4:
            severity = "Minimal"
            description = "Minimal or no depression symptoms"
        elif total_score <= 9:
            severity = "Mild"
            description = "Mild depression symptoms"
        elif total_score <= 14:
            severity = "Moderate"
            description = "Moderate depression symptoms"
        elif total_score <= 19:
            severity = "Moderately Severe"
            description = "Moderately severe depression symptoms"
        else:
            severity = "Severe"
            description = "Severe depression symptoms"

        return {
            "severity_level": severity,
            "description": description,
            "score": total_score,
            "interpretation": f"PHQ-9 score of {total_score} suggests {severity.lower()} depression"
        }

    @staticmethod
    def get_severity_level(total_score: int) -> str:
        """Get severity level string"""
        return PHQResponseService.get_score_analysis(total_score)["severity_level"]

    @staticmethod
    def is_assessment_complete(session_id: int) -> bool:
        """Check if PHQ assessment is complete for session"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                return False

            # Check if PHQ completion timestamp exists
            return session.phq_completed_at is not None

    @staticmethod
    def get_response_count(session_id: int) -> int:
        """Get number of responses completed for session"""
        with get_session() as db:
            return db.query(PHQResponse).filter_by(session_id=session_id).count()

    @staticmethod
    def get_expected_response_count(session_id: int) -> int:
        """Get expected number of responses for session based on settings"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                return 0

            phq_settings = session.phq_settings
            active_categories = len(PHQCategoryType.get_all_categories())

            return active_categories * phq_settings.questions_per_category

    @staticmethod
    def get_max_possible_score(session_id: int) -> int:
        """Get maximum possible score for session"""
        expected_responses = PHQResponseService.get_expected_response_count(session_id)
        return expected_responses * 3  # Max score per question is 3
