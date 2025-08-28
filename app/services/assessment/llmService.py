# app/services/assessment/llmService.py
from typing import List, Dict, Any, Optional
import re
import requests
from datetime import datetime
from ...model.assessment.sessions import AssessmentSession, LLMConversationTurn, LLMAnalysisResult
from ...model.admin.llm import OpenQuestionSettings
from ...db import get_session
from ...services.admin.llmService import LLMService as AdminLLMService


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
    def create_conversation_turn(
        session_id: int,
        turn_number: int,
        ai_message: str,
        user_message: str,
        ai_model_used: Optional[str] = None,
        response_audio_path: Optional[str] = None,
        transcription: Optional[str] = None
    ) -> LLMConversationTurn:
        """Create a new conversation turn"""
        with get_session() as db:
            # Check for </end_conversation> in AI message
            has_end_conversation = "</end_conversation>" in ai_message.lower()
            
            turn = LLMConversationTurn(
                session_id=session_id,
                turn_number=turn_number,
                ai_message=ai_message,
                user_message=user_message,
                has_end_conversation=has_end_conversation,
                user_message_length=len(user_message),
                ai_model_used=ai_model_used,
                response_audio_path=response_audio_path,
                transcription=transcription
            )
            
            db.add(turn)
            db.commit()
            
            # If conversation ended, trigger analysis
            if has_end_conversation:
                LLMConversationService.trigger_analysis(session_id)
            
            return turn
    
    @staticmethod
    def get_session_conversations(session_id: int) -> List[LLMConversationTurn]:
        """Get all conversation turns for a session"""
        with get_session() as db:
            return db.query(LLMConversationTurn).filter_by(session_id=session_id).order_by(LLMConversationTurn.turn_number).all()
    
    @staticmethod
    def get_conversation_by_id(turn_id: int) -> Optional[LLMConversationTurn]:
        """Get a specific conversation turn by ID"""
        with get_session() as db:
            return db.query(LLMConversationTurn).filter_by(id=turn_id).first()
    
    @staticmethod
    def update_conversation_turn(turn_id: int, updates: Dict[str, Any]) -> LLMConversationTurn:
        """Update a conversation turn"""
        with get_session() as db:
            turn = db.query(LLMConversationTurn).filter_by(id=turn_id).first()
            if not turn:
                raise ValueError(f"Conversation turn with ID {turn_id} not found")
            
            for key, value in updates.items():
                if hasattr(turn, key):
                    setattr(turn, key, value)
            
            # Update user_message_length if user_message changed
            if 'user_message' in updates:
                turn.user_message_length = len(updates['user_message'])
            
            # Check for end conversation if ai_message changed
            if 'ai_message' in updates:
                turn.has_end_conversation = "</end_conversation>" in updates['ai_message'].lower()
            
            db.commit()
            return turn
    
    @staticmethod
    def delete_conversation_turn(turn_id: int) -> bool:
        """Delete a conversation turn"""
        with get_session() as db:
            turn = db.query(LLMConversationTurn).filter_by(id=turn_id).first()
            if not turn:
                raise ValueError(f"Conversation turn with ID {turn_id} not found")
            
            db.delete(turn)
            db.commit()
            return True
    
    @staticmethod
    def trigger_analysis(session_id: int) -> LLMAnalysisResult:
        """Trigger LLM analysis when conversation ends"""
        with get_session() as db:
            # Get session and its LLM settings
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            # Get all conversation turns
            conversations = db.query(LLMConversationTurn).filter_by(session_id=session_id).order_by(LLMConversationTurn.turn_number).all()
            if not conversations:
                raise ValueError("No conversation turns found for analysis")
            
            # Build conversation text for analysis
            conversation_text = LLMConversationService._build_conversation_text(conversations)
            
            # Get LLM settings used for this session
            llm_settings = session.llm_settings
            
            # Get aspects and standardize keys
            aspects = llm_settings.depression_aspects.get('aspects', [])
            standardized_aspects = []
            
            for aspect in aspects:
                if isinstance(aspect, dict):
                    std_key = LLMConversationService.standardize_aspect_key(aspect.get('name', ''))
                    standardized_aspects.append({
                        "key": std_key,
                        "name": aspect.get('name', ''),
                        "description": aspect.get('description', '')
                    })
            
            # Build analysis prompt with standardized keys
            analysis_prompt = AdminLLMService.build_analysis_prompt(aspects)
            
            # Call OpenAI for analysis
            analysis_result = LLMConversationService._call_analysis_api(
                conversation_text,
                analysis_prompt,
                llm_settings.openai_api_key,
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
    def _build_conversation_text(conversations: List[LLMConversationTurn]) -> str:
        """Build conversation text for analysis"""
        conversation_parts = []
        
        for turn in conversations:
            conversation_parts.append(f"Anisa: {turn.ai_message}")
            conversation_parts.append(f"Teman: {turn.user_message}")
        
        return "\n\n".join(conversation_parts)
    
    @staticmethod
    def _call_analysis_api(conversation_text: str, analysis_prompt: str, api_key: str, model: str) -> Dict[str, Any]:
        """Call OpenAI API for conversation analysis"""
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': analysis_prompt},
                {'role': 'user', 'content': conversation_text}
            ],
            'temperature': 0.3,  # Lower temperature for more consistent analysis
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
    def get_session_analysis(session_id: int) -> Optional[LLMAnalysisResult]:
        """Get analysis result for a session"""
        with get_session() as db:
            return db.query(LLMAnalysisResult).filter_by(session_id=session_id).first()
    
    @staticmethod
    def check_conversation_complete(session_id: int) -> bool:
        """Check if conversation has ended (contains </end_conversation>)"""
        with get_session() as db:
            end_turn = db.query(LLMConversationTurn).filter_by(
                session_id=session_id,
                has_end_conversation=True
            ).first()
            
            return end_turn is not None
    
    @staticmethod
    def get_conversation_summary(session_id: int) -> Dict[str, Any]:
        """Get summary of conversation for a session"""
        with get_session() as db:
            conversations = db.query(LLMConversationTurn).filter_by(session_id=session_id).all()
            analysis = db.query(LLMAnalysisResult).filter_by(session_id=session_id).first()
            
            total_turns = len(conversations)
            total_user_words = sum(len(turn.user_message.split()) for turn in conversations)
            avg_response_length = sum(turn.user_message_length for turn in conversations) / total_turns if total_turns > 0 else 0
            
            return {
                "total_conversation_turns": total_turns,
                "total_user_words": total_user_words,
                "average_response_length": avg_response_length,
                "conversation_completed": any(turn.has_end_conversation for turn in conversations),
                "analysis_completed": analysis is not None,
                "analysis_summary": {
                    "total_aspects_detected": analysis.total_aspects_detected if analysis else 0,
                    "average_severity_score": analysis.average_severity_score if analysis else 0,
                    "model_used": analysis.analysis_model_used if analysis else None
                } if analysis else None
            }