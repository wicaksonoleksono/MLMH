# app/services/assessment/llmService.py
from typing import List, Dict, Any, Optional
import re
import requests
from datetime import datetime
from ...model.assessment.sessions import AssessmentSession, LLMConversation, LLMAnalysisResult
from ...db import get_session
from ...services.admin.llmService import LLMService as AdminLLMService
from ...services.llm.analysisPromptBuilder import LLMAnalysisPromptBuilder


class LLMConversationService:
    """Service for handling LLM conversation turns and analysis with CRUD operations"""
    
    @staticmethod
    def standardize_aspect_key(aspect_name: str) -> str:
        """Convert aspect name to standardized lowercase key with underscores"""
        # "Anhedonia" -> "anhedonia"
        # "Bias kognitif negatif" -> "bias_kognitif_negatif"
        # "Defisit regulasi emosi" -> "defisit_regulasi_emosi"
        return aspect_name.lower().replace(" ", "_").replace("-", "_")
    
    @staticmethod
    def create_empty_conversation_record(session_id: str) -> LLMConversation:
        """Create empty LLM conversation record immediately on assessment start (assessment-first approach)"""
        with get_session() as db:
            # Get session for validation
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")

            # Check if LLM conversation record already exists
            existing_record = db.query(LLMConversation).filter_by(session_id=session_id).first()
            if existing_record:
                return existing_record

            # Create empty LLM conversation record
            conversation_record = LLMConversation(
                session_id=session_id,
                conversation_history={"turns": []}  # Empty turns array, will be populated later
            )
            db.add(conversation_record)
            db.commit()
            db.refresh(conversation_record)
            
            return conversation_record

    @staticmethod
    def create_conversation_turn(
        session_id: str,
        turn_number: int,
        ai_message: str,
        user_message: str,
        ai_model_used: Optional[str] = None,
        response_audio_path: Optional[str] = None,
        transcription: Optional[str] = None
    ) -> LLMConversation:
        """Create or update conversation turn in single JSON record"""
        with get_session() as db:
            # Get existing LLM conversation record for this session or create new one
            conversation_record = db.query(LLMConversation).filter_by(session_id=session_id).first()
            if not conversation_record:
                conversation_record = LLMConversation(
                    session_id=session_id,
                    conversation_history={"turns": []}
                )
                db.add(conversation_record)

            # Create turn data with more robust end conversation detection
            normalized_ai_message = ai_message.lower().strip()
            has_end_conversation = (
                "</end_conversation>" in normalized_ai_message or 
                "<end_conversation>" in normalized_ai_message or 
                "\u003c/end_conversation\u003e" in normalized_ai_message
            )
            
            turn_data = {
                "turn_number": turn_number,
                "ai_message": ai_message,
                "user_message": user_message,
                "has_end_conversation": has_end_conversation,
                "user_message_length": len(user_message),
                "ai_model_used": ai_model_used,
                "response_audio_path": response_audio_path,
                "transcription": transcription,
                "created_at": datetime.utcnow().isoformat()
            }

            turns = conversation_record.conversation_history.get("turns", [])
            turn_exists = False
            for i, existing_turn in enumerate(turns):
                if existing_turn.get("turn_number") == turn_number:
                    turns[i] = turn_data
                    turn_exists = True
                    break
            
            if not turn_exists:
                turns.append(turn_data)
            
            # Sort turns by turn number
            turns.sort(key=lambda x: x.get("turn_number", 0))
            
            # Create completely new JSON object to force SQLAlchemy to detect change
            conversation_record.conversation_history = {
                "turns": turns,
                "total_turns": len(turns),
                "last_updated": datetime.utcnow().isoformat()
            }

            db.commit()
            return conversation_record
    
    @staticmethod
    def get_session_conversations(session_id: str) -> List[Dict[str, Any]]:
        """Get all conversation turns for a session from single JSON record"""
        with get_session() as db:
            conversation_record = db.query(LLMConversation).filter_by(session_id=session_id).first()
            if not conversation_record:
                return []
            
            return conversation_record.conversation_history.get("turns", [])
    
    @staticmethod
    def get_conversation_by_id(session_id: str) -> Optional[LLMConversation]:
        """Get the conversation record by session ID"""
        with get_session() as db:
            return db.query(LLMConversation).filter_by(session_id=session_id).first()
    
    @staticmethod
    def update_conversation_turn(session_id: str, turn_number: int, updates: Dict[str, Any]) -> LLMConversation:
        """Update a conversation turn in the single JSON record"""
        with get_session() as db:
            conversation_record = db.query(LLMConversation).filter_by(session_id=session_id).first()
            if not conversation_record:
                raise ValueError(f"Conversation record for session {session_id} not found")
            
            turns = conversation_record.conversation_history.get("turns", [])
            
            # Find the turn to update
            turn_found = False
            for i, turn in enumerate(turns):
                if turn.get("turn_number") == turn_number:
                    # Update the turn data
                    turns[i].update(updates)
                    
                    # Update computed fields if relevant fields changed
                    if 'user_message' in updates:
                        turns[i]["user_message_length"] = len(updates['user_message'])
                    
                    if 'ai_message' in updates:
                        turns[i]["has_end_conversation"] = "</end_conversation>" in updates['ai_message'].lower()
                    
                    turn_found = True
                    break
            
            if not turn_found:
                raise ValueError(f"Conversation turn {turn_number} not found for session {session_id}")
            
            # Update conversation history
            conversation_record.conversation_history["turns"] = turns
            # Note: Model doesn't have updated_at field
            
            db.commit()
            return conversation_record
    
    @staticmethod
    def delete_conversation_turn(session_id: str, turn_number: int) -> bool:
        """Delete a conversation turn from the single JSON record"""
        with get_session() as db:
            conversation_record = db.query(LLMConversation).filter_by(session_id=session_id).first()
            if not conversation_record:
                raise ValueError(f"Conversation record for session {session_id} not found")
            
            turns = conversation_record.conversation_history.get("turns", [])
            
            # Find and remove the turn
            turn_found = False
            for i, turn in enumerate(turns):
                if turn.get("turn_number") == turn_number:
                    turns.pop(i)
                    turn_found = True
                    break
            
            if not turn_found:
                raise ValueError(f"Conversation turn {turn_number} not found for session {session_id}")
            
            # Update conversation history
            conversation_record.conversation_history["turns"] = turns
            # Note: Model doesn't have updated_at field
            
            db.commit()
            return True
    
    @staticmethod
    def trigger_analysis(session_id: str) -> LLMAnalysisResult:
        """Trigger LLM analysis when conversation ends"""
        with get_session() as db:
            # Get session and its LLM settings
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            # Get conversation record
            conversation_record = db.query(LLMConversation).filter_by(session_id=session_id).first()
            if not conversation_record:
                raise ValueError("No conversation record found for analysis")
            
            # Get all conversation turns
            conversations = conversation_record.conversation_history.get("turns", [])
            if not conversations:
                raise ValueError("No conversation turns found for analysis")
            
            # Get LLM settings used for this session
            llm_settings = session.llm_settings
            
            # Get aspects and analysis scale
            aspects = llm_settings.depression_aspects.get('aspects', [])
            
            # Extract analysis scale from settings - REQUIRED
            analysis_scale = None
            if llm_settings.analysis_scale:
                if isinstance(llm_settings.analysis_scale, dict) and 'scale' in llm_settings.analysis_scale:
                    analysis_scale = llm_settings.analysis_scale['scale']
                elif isinstance(llm_settings.analysis_scale, list):
                    analysis_scale = llm_settings.analysis_scale
            
            if not analysis_scale:
                raise ValueError("Analysis scale not configured in LLM settings")
            
            # Convert conversations to message format for modern prompt builder
            conversation_messages = []
            for turn in conversations:
                if turn.get('ai_message'):
                    conversation_messages.append({
                        "role": "assistant",
                        "message": turn.get('ai_message')
                    })
                if turn.get('user_message'):
                    conversation_messages.append({
                        "role": "user",
                        "message": turn.get('user_message')
                    })
            
            # Build analysis prompt using modern prompt builder with configurable scale
            analysis_prompt = LLMAnalysisPromptBuilder.build_full_analysis_prompt(
                conversation_messages=conversation_messages,
                depression_aspects=aspects,
                analysis_scale=analysis_scale
            )
            
            # Get standardized aspects for result processing
            standardized_aspects = []
            for aspect in aspects:
                if isinstance(aspect, dict):
                    std_key = LLMConversationService.standardize_aspect_key(aspect.get('name', ''))
                    standardized_aspects.append({
                        "key": std_key,
                        "name": aspect.get('name', ''),
                        "description": aspect.get('description', '')
                    })
            
            # Call OpenAI for analysis
            analysis_result = LLMConversationService._call_analysis_api(
                analysis_prompt,
                llm_settings.get_api_key(),
                llm_settings.analysis_model
            )
            
            # Process and standardize the analysis result
            processed_scores = LLMConversationService._process_analysis_result(analysis_result, standardized_aspects)
            
            # Calculate summary statistics
            total_aspects = len([score for score in processed_scores.values() if score.get('indicator_score', 0) > 0])
            avg_severity = sum(score.get('indicator_score', 0) for score in processed_scores.values()) / len(processed_scores) if processed_scores else 0
            
            # Store analysis result
            analysis_record = LLMAnalysisResult(
                session_id=session_id,
                analysis_model_used=llm_settings.analysis_model,
                conversation_turns_analyzed=len(conversations),
                raw_analysis_result=analysis_result,
                aspect_scores=processed_scores,
                total_aspects_detected=total_aspects,
                average_severity_score=avg_severity
            )
            
            db.add(analysis_record)
            db.commit()
            
            return analysis_record
    
    @staticmethod
    def _build_conversation_text(conversations: List[LLMConversation]) -> str:
        """Build conversation text for analysis"""
        conversation_parts = []
        
        for turn in conversations:
            conversation_parts.append(f"Anisa: {turn.ai_message}")
            conversation_parts.append(f"Teman: {turn.user_message}")
        
        return "\n\n".join(conversation_parts)
    
    @staticmethod
    def _call_analysis_api(analysis_prompt: str, api_key: str, model: str) -> Dict[str, Any]:
        """Call OpenAI API for conversation analysis using modern prompt builder"""
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': 'You are a professional psychologist analyzing conversation transcripts. Respond only with the requested JSON format.'},
                {'role': 'user', 'content': analysis_prompt}
            ],
            'temperature': 0,  # Lower temperature for more consistent analysis
            'max_tokens': 2000
        }
        
        try:
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # Try to parse as JSON
            import json
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # If not valid JSON, return as text
                return {"raw_response": content}
                
        except Exception as e:
            raise ValueError(f"Analysis API call failed: {str(e)}")
    
    @staticmethod
    def _process_analysis_result(raw_result: Dict[str, Any], standardized_aspects: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Process raw analysis result and standardize aspect keys"""
        processed_scores = {}
        
        # Create mapping from original names to standardized keys
        name_to_key = {aspect['name']: aspect['key'] for aspect in standardized_aspects}
        
        for original_name, analysis_data in raw_result.items():
            if original_name == "raw_response":
                continue
                
            # Find standardized key
            std_key = name_to_key.get(original_name, LLMConversationService.standardize_aspect_key(original_name))
            
            if isinstance(analysis_data, dict):
                processed_scores[std_key] = {
                    "original_name": original_name,
                    "explanation": analysis_data.get("explanation", ""),
                    "indicator_score": analysis_data.get("indicator_score", 0)
                }
            else:
                processed_scores[std_key] = {
                    "original_name": original_name,
                    "explanation": str(analysis_data),
                    "indicator_score": 0
                }
        
        return processed_scores
    
    @staticmethod
    def get_session_analysis(session_id: str) -> Optional[LLMAnalysisResult]:
        """Get analysis result for a session"""
        with get_session() as db:
            return db.query(LLMAnalysisResult).filter_by(session_id=session_id).first()
    
    @staticmethod
    def check_conversation_complete(session_id: str) -> bool:
        """Check if conversation has ended (contains </end_conversation>)"""
        with get_session() as db:
            conversation_record = db.query(LLMConversation).filter_by(session_id=session_id).first()
            if not conversation_record:
                return False
            
            turns = conversation_record.conversation_history.get("turns", [])
            for i, turn in enumerate(turns):
                has_end = turn.get("has_end_conversation", False)
                ai_msg = turn.get("ai_message", "")
                if has_end:
                    return True
            return False
    
    @staticmethod
    def get_conversation_summary(session_id: str) -> Dict[str, Any]:
        """Get summary of conversation for a session"""
        with get_session() as db:
            conversation_record = db.query(LLMConversation).filter_by(session_id=session_id).first()
            conversations = conversation_record.conversation_history.get("turns", []) if conversation_record else []
            analysis = db.query(LLMAnalysisResult).filter_by(session_id=session_id).first()
            
            total_turns = len(conversations)
            total_user_words = sum(len(turn.get("user_message", "").split()) for turn in conversations)
            avg_response_length = sum(turn.get("user_message_length", 0) for turn in conversations) / total_turns if total_turns > 0 else 0
            
            return {
                "total_conversation_turns": total_turns,
                "total_user_words": total_user_words,
                "average_response_length": avg_response_length,
                "conversation_completed": any(turn.get("has_end_conversation", False) for turn in conversations),
                "analysis_completed": analysis is not None,
                "analysis_summary": {
                    "total_aspects_detected": analysis.total_aspects_detected if analysis else 0,
                    "average_severity_score": analysis.average_severity_score if analysis else 0,
                    "model_used": analysis.analysis_model_used if analysis else None
                } if analysis else None
            }

    @staticmethod
    def clear_session_conversations(session_id: str) -> int:
        """Clear all LLM conversations and analysis for a session - used for restart functionality"""
        with get_session() as db:
            conversation_record = db.query(LLMConversation).filter_by(session_id=session_id).first()
            analysis_records = db.query(LLMAnalysisResult).filter_by(session_id=session_id).all()
            
            total_count = 0
            if conversation_record:
                total_count += 1
                db.delete(conversation_record)
                
            total_count += len(analysis_records)
            for analysis in analysis_records:
                db.delete(analysis)
            
            db.commit()
            return total_count