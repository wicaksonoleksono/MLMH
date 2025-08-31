# app/services/llm/analysisResultProcessor.py
from typing import Dict, Any, List, Optional, Tuple
import json
import re
from ...model.assessment.sessions import LLMAnalysisResult, AssessmentSession
from ...db import get_session


class LLMAnalysisResultProcessor:
    """
    Processes and stores LLM analysis results.
    Handles JSON parsing, validation, and database storage.
    """
    
    @staticmethod
    def extract_json_from_response(raw_response: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from LLM response, handling various formatting issues.
        
        Args:
            raw_response: Raw text response from LLM
            
        Returns:
            Parsed JSON dict or None if extraction fails
        """
        if not raw_response or not raw_response.strip():
            return None
        
        # Clean the response - remove markdown code blocks if present
        cleaned_response = raw_response.strip()
        cleaned_response = re.sub(r'^```json\s*', '', cleaned_response, flags=re.MULTILINE)
        cleaned_response = re.sub(r'^```\s*$', '', cleaned_response, flags=re.MULTILINE)
        cleaned_response = cleaned_response.strip()
        
        # Try to find JSON within the text
        json_patterns = [
            # Full response is JSON
            r'^(\{.*\})$',
            # JSON wrapped in text
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
            # JSON with nested objects
            r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, cleaned_response, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
        
        # If no pattern works, try parsing the cleaned response directly
        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def validate_analysis_result(
        json_result: Dict[str, Any], 
        expected_aspects: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str]]:
        """
        Validate the parsed JSON result against expected structure.
        
        Args:
            json_result: Parsed JSON from LLM
            expected_aspects: List of depression aspects that should be analyzed
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        if not isinstance(json_result, dict):
            errors.append("Result is not a dictionary")
            return False, errors
        
        # Check if we have results for depression aspects
        expected_keys = [
            aspect.get('name', '').lower().replace(' ', '_') 
            for aspect in expected_aspects
        ]
        
        for key in expected_keys:
            if key not in json_result:
                errors.append(f"Missing analysis for aspect: {key}")
                continue
                
            aspect_result = json_result[key]
            if not isinstance(aspect_result, dict):
                errors.append(f"Invalid format for aspect {key}: not a dictionary")
                continue
                
            # Check required fields
            if 'penjelasan' not in aspect_result:
                errors.append(f"Missing 'penjelasan' for aspect {key}")
            if 'skor' not in aspect_result:
                errors.append(f"Missing 'skor' for aspect {key}")
            else:
                # Validate score range
                score = aspect_result['skor']
                if not isinstance(score, (int, float)) or not (0 <= score <= 3):
                    errors.append(f"Invalid score for aspect {key}: {score} (must be 0-3)")
        
        return len(errors) == 0, errors

    @staticmethod
    def calculate_analysis_metrics(aspect_scores: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate aggregate metrics from individual aspect scores.
        
        Args:
            aspect_scores: Dictionary of aspect results with scores
            
        Returns:
            Dictionary with calculated metrics
        """
        scores = []
        
        for aspect_key, aspect_data in aspect_scores.items():
            if isinstance(aspect_data, dict) and 'skor' in aspect_data:
                score = aspect_data['skor']
                if isinstance(score, (int, float)) and 0 <= score <= 3:
                    scores.append(float(score))
        
        if not scores:
            return {
                'total_aspects_detected': 0,
                'average_severity_score': 0.0,
                'analysis_confidence': 0.0
            }
        
        # Count aspects with score > 0 (detected symptoms)
        detected_count = sum(1 for score in scores if score > 0)
        
        # Calculate average severity
        avg_severity = sum(scores) / len(scores)
        
        # Calculate confidence based on consistency of scores
        # (This is a simple heuristic - could be improved)
        score_variance = sum((s - avg_severity) ** 2 for s in scores) / len(scores)
        confidence = max(0.0, 1.0 - (score_variance / 2.25))  # 2.25 is max possible variance for 0-3 scale
        
        return {
            'total_aspects_detected': detected_count,
            'average_severity_score': round(avg_severity, 2),
            'analysis_confidence': round(confidence, 2)
        }

    @staticmethod
    def store_analysis_result(
        session_id: str,
        analysis_model_used: str,
        conversation_turns_analyzed: int,
        raw_llm_response: str,
        parsed_result: Dict[str, Any],
        depression_aspects: List[Dict[str, Any]]
    ) -> Optional[LLMAnalysisResult]:
        """
        Store analysis result in database.
        
        Args:
            session_id: Assessment session ID
            analysis_model_used: OpenAI model used for analysis
            conversation_turns_analyzed: Number of conversation turns analyzed
            raw_llm_response: Raw response from LLM
            parsed_result: Parsed and validated JSON result
            depression_aspects: Original aspects configuration
            
        Returns:
            Created LLMAnalysisResult or None if storage fails
        """
        try:
            with get_session() as db:
                # Verify session exists
                session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
                if not session:
                    print(f"❌ Session {session_id} not found for analysis storage")
                    return None
                
                # Calculate metrics
                metrics = LLMAnalysisResultProcessor.calculate_analysis_metrics(parsed_result)
                
                # Create analysis result record
                analysis_result = LLMAnalysisResult(
                    session_id=session_id,
                    analysis_model_used=analysis_model_used,
                    conversation_turns_analyzed=conversation_turns_analyzed,
                    raw_analysis_result={'llm_response': raw_llm_response, 'parsed_json': parsed_result},
                    aspect_scores=parsed_result,
                    total_aspects_detected=metrics['total_aspects_detected'],
                    average_severity_score=metrics['average_severity_score'],
                    analysis_confidence=metrics['analysis_confidence']
                )
                
                db.add(analysis_result)
                db.commit()
                
                print(f"✅ Stored analysis result for session {session_id}")
                print(f"   Detected aspects: {metrics['total_aspects_detected']}")
                print(f"   Average severity: {metrics['average_severity_score']}")
                print(f"   Confidence: {metrics['analysis_confidence']}")
                
                return analysis_result
                
        except Exception as e:
            print(f"❌ Error storing analysis result: {str(e)}")
            return None

    @classmethod
    def process_llm_analysis_response(
        cls,
        session_id: str,
        raw_llm_response: str,
        analysis_model_used: str,
        conversation_turns_analyzed: int,
        depression_aspects: List[Dict[str, Any]]
    ) -> Optional[LLMAnalysisResult]:
        """
        Complete processing pipeline for LLM analysis response.
        
        Args:
            session_id: Assessment session ID
            raw_llm_response: Raw text response from LLM
            analysis_model_used: Model used for analysis
            conversation_turns_analyzed: Number of turns analyzed
            depression_aspects: Aspects configuration used
            
        Returns:
            LLMAnalysisResult if successful, None if processing failed
        """
        print(f"🔍 Processing analysis response for session {session_id}")
        
        # Extract JSON from response
        parsed_result = cls.extract_json_from_response(raw_llm_response)
        if parsed_result is None:
            print(f"❌ Failed to extract JSON from LLM response")
            return None
        
        # Validate the result
        is_valid, errors = cls.validate_analysis_result(parsed_result, depression_aspects)
        if not is_valid:
            print(f"❌ Analysis result validation failed:")
            for error in errors:
                print(f"   - {error}")
            return None
        
        print(f"✅ Analysis result validated successfully")
        
        # Store in database
        return cls.store_analysis_result(
            session_id=session_id,
            analysis_model_used=analysis_model_used,
            conversation_turns_analyzed=conversation_turns_analyzed,
            raw_llm_response=raw_llm_response,
            parsed_result=parsed_result,
            depression_aspects=depression_aspects
        )