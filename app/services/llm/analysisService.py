# app/services/llm/analysisService.py
from typing import List, Dict, Any, Optional
import openai
from flask import current_app
from ...model.assessment.sessions import AssessmentSession, LLMConversation, LLMAnalysisResult
from ...model.admin.llm import LLMSettings
from ...db import get_session
from .analysisPromptBuilder import LLMAnalysisPromptBuilder
from .analysisResultProcessor import LLMAnalysisResultProcessor


class LLMAnalysisService:
    """
    Core service for running LLM conversation analysis.
    Orchestrates prompt building, LLM API calls, and result processing.
    """
    
    # Fixed analysis parameters as per requirements
    ANALYSIS_SEED = 42
    ANALYSIS_TEMPERATURE = 0.0
    MAX_TOKENS = 2000
    
    @staticmethod
    def get_llm_settings() -> Optional[LLMSettings]:
        """Get active LLM settings for analysis."""
        with get_session() as db:
            return db.query(LLMSettings).filter(LLMSettings.is_active == True).first()
    
    @staticmethod
    def get_conversation_messages(session_id: str) -> List[Dict[str, str]]:
        """
        Retrieve conversation messages for a session.
        
        Args:
            session_id: Assessment session ID
            
        Returns:
            List of conversation messages in format [{"role": "user|assistant", "message": "content"}]
        """
        with get_session() as db:
            conversations = db.query(LLMConversation).filter(
                LLMConversation.session_id == session_id
            ).order_by(LLMConversation.created_at.asc()).all()
            
            messages = []
            for conv in conversations:
                # Add user message
                if conv.user_message:
                    messages.append({
                        "role": "user",
                        "message": conv.user_message
                    })
                
                # Add assistant message
                if conv.assistant_message:
                    messages.append({
                        "role": "assistant", 
                        "message": conv.assistant_message
                    })
            
            return messages
    
    @staticmethod
    def call_openai_analysis(
        analysis_prompt: str, 
        api_key: str, 
        model: str = "gpt-4o-mini"
    ) -> Optional[str]:
        """
        Make OpenAI API call for analysis with fixed parameters.
        
        Args:
            analysis_prompt: Complete analysis prompt
            api_key: OpenAI API key
            model: Model to use (from settings)
            
        Returns:
            Raw response text or None if API call fails
        """
        try:
            client = openai.OpenAI(api_key=api_key)
            
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a professional psychologist analyzing conversation transcripts. Respond only with the requested JSON format."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=LLMAnalysisService.ANALYSIS_TEMPERATURE,
                seed=LLMAnalysisService.ANALYSIS_SEED,
                max_tokens=LLMAnalysisService.MAX_TOKENS,
                response_format={"type": "json_object"}  # Force JSON response
            )
            
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content
            else:
                print(" No response choices returned from OpenAI")
                return None
                
        except Exception as e:
            print(f" OpenAI API call failed: {str(e)}")
            return None
    
    @staticmethod
    def validate_session_for_analysis(session_id: str) -> Optional[AssessmentSession]:
        """
        Validate that session exists and has completed LLM conversation.
        
        Args:
            session_id: Session to validate
            
        Returns:
            AssessmentSession if valid, None otherwise
        """
        with get_session() as db:
            session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
            
            if not session:
                print(f" Session {session_id} not found")
                return None
            
            if not session.llm_completed_at:
                print(f" Session {session_id} has not completed LLM assessment yet")
                return None
            
            # Check if analysis already exists
            existing_analysis = db.query(LLMAnalysisResult).filter(
                LLMAnalysisResult.session_id == session_id
            ).first()
            
            if existing_analysis:
                print(f"⚠️  Analysis already exists for session {session_id}")
                # Could return the existing analysis or proceed with new one
                # For now, we'll proceed with new analysis
            
            return session
    
    @classmethod
    def run_conversation_analysis(cls, session_id: str) -> Optional[LLMAnalysisResult]:
        """
        Run complete conversation analysis for a session.
        
        Args:
            session_id: Assessment session ID to analyze
            
        Returns:
            LLMAnalysisResult if successful, None if analysis failed
        """
        print(f"🚀 Starting conversation analysis for session {session_id}")
        
        # 1. Validate session
        session = cls.validate_session_for_analysis(session_id)
        if not session:
            return None
        
        # 2. Get LLM settings
        llm_settings = cls.get_llm_settings()
        if not llm_settings:
            print(" No active LLM settings found")
            return None
        
        api_key = llm_settings.get_api_key()
        if not api_key:
            print(" No valid API key in LLM settings")
            return None
        
        # 3. Get depression aspects configuration
        depression_aspects = []
        analysis_scale = None
        if llm_settings.depression_aspects:
            if isinstance(llm_settings.depression_aspects, dict) and 'aspects' in llm_settings.depression_aspects:
                depression_aspects = llm_settings.depression_aspects['aspects']
            elif isinstance(llm_settings.depression_aspects, list):
                depression_aspects = llm_settings.depression_aspects
        
        # Get analysis scale if available
        if llm_settings.analysis_scale:
            if isinstance(llm_settings.analysis_scale, dict) and 'scale' in llm_settings.analysis_scale:
                analysis_scale = llm_settings.analysis_scale['scale']
            elif isinstance(llm_settings.analysis_scale, list):
                analysis_scale = llm_settings.analysis_scale
        
        if not depression_aspects:
            print(" No depression aspects configured in LLM settings")
            return None
        
        # 4. Get conversation messages
        conversation_messages = cls.get_conversation_messages(session_id)
        if not conversation_messages:
            print(f" No conversation messages found for session {session_id}")
            return None
        
        print(f"📝 Found {len(conversation_messages)} conversation messages")
        
        # 5. Build analysis prompt
        analysis_prompt = LLMAnalysisPromptBuilder.build_full_analysis_prompt(
            conversation_messages=conversation_messages,
            depression_aspects=depression_aspects,
            analysis_scale=analysis_scale
        )
        
        print(f"🔧 Built analysis prompt ({len(analysis_prompt)} characters)")
        
        # 6. Call OpenAI API
        analysis_model = llm_settings.analysis_model or "gpt-4o-mini"
        raw_response = cls.call_openai_analysis(
            analysis_prompt=analysis_prompt,
            api_key=api_key,
            model=analysis_model
        )
        
        if not raw_response:
            print(" Failed to get response from OpenAI")
            return None
        
        print(f"🤖 Got response from OpenAI ({len(raw_response)} characters)")
        
        # 7. Process and store results
        result = LLMAnalysisResultProcessor.process_llm_analysis_response(
            session_id=session_id,
            raw_llm_response=raw_response,
            analysis_model_used=analysis_model,
            conversation_turns_analyzed=len(conversation_messages),
            depression_aspects=depression_aspects
        )
        
        if result:
            print(f"✅ Analysis completed successfully for session {session_id}")
            print(f"   Analysis ID: {result.id}")
            print(f"   Aspects detected: {result.total_aspects_detected}")
            print(f"   Average severity: {result.average_severity_score}")
        else:
            print(f" Failed to process analysis results for session {session_id}")
        
        return result
    
    @staticmethod
    def get_analysis_result(session_id: str) -> Optional[LLMAnalysisResult]:
        """
        Get existing analysis result for a session.
        
        Args:
            session_id: Session ID to get analysis for
            
        Returns:
            LLMAnalysisResult if exists, None otherwise
        """
        with get_session() as db:
            return db.query(LLMAnalysisResult).filter(
                LLMAnalysisResult.session_id == session_id
            ).first()
    
    @staticmethod
    def test_analysis_with_sample_data(sample_conversation: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Test analysis functionality with sample conversation data.
        
        Args:
            sample_conversation: List of sample messages
            
        Returns:
            Dictionary with test results
        """
        try:
            # Get LLM settings
            llm_settings = LLMAnalysisService.get_llm_settings()
            if not llm_settings:
                return {"status": "error", "message": "No active LLM settings found"}
            
            api_key = llm_settings.get_api_key()
            if not api_key:
                return {"status": "error", "message": "No valid API key in LLM settings"}
            
            # Get depression aspects
            depression_aspects = []
            analysis_scale = None
            if llm_settings.depression_aspects:
                if isinstance(llm_settings.depression_aspects, dict) and 'aspects' in llm_settings.depression_aspects:
                    depression_aspects = llm_settings.depression_aspects['aspects']
                elif isinstance(llm_settings.depression_aspects, list):
                    depression_aspects = llm_settings.depression_aspects
            
            # Get analysis scale if available
            if llm_settings.analysis_scale:
                if isinstance(llm_settings.analysis_scale, dict) and 'scale' in llm_settings.analysis_scale:
                    analysis_scale = llm_settings.analysis_scale['scale']
                elif isinstance(llm_settings.analysis_scale, list):
                    analysis_scale = llm_settings.analysis_scale
            
            if not depression_aspects:
                return {"status": "error", "message": "No depression aspects configured"}
            
            # Build prompt
            analysis_prompt = LLMAnalysisPromptBuilder.build_full_analysis_prompt(
                conversation_messages=sample_conversation,
                depression_aspects=depression_aspects,
                analysis_scale=analysis_scale
            )
            
            # Make API call
            analysis_model = llm_settings.analysis_model or "gpt-4o-mini"
            raw_response = LLMAnalysisService.call_openai_analysis(
                analysis_prompt=analysis_prompt,
                api_key=api_key,
                model=analysis_model
            )
            
            if not raw_response:
                return {"status": "error", "message": "Failed to get response from OpenAI"}
            
            # Process response (but don't store)
            parsed_result = LLMAnalysisResultProcessor.extract_json_from_response(raw_response)
            is_valid, errors = LLMAnalysisResultProcessor.validate_analysis_result(parsed_result, depression_aspects)
            
            return {
                "status": "success",
                "prompt_length": len(analysis_prompt),
                "response_length": len(raw_response),
                "parsed_successfully": parsed_result is not None,
                "validation_passed": is_valid,
                "validation_errors": errors,
                "parsed_result": parsed_result,
                "raw_response": raw_response
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}