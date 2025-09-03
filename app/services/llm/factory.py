# app/services/llm/factory.py
"""
LLM Factory for creating ChatOpenAI instances based on session settings
"""

from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI
from ...model.admin.llm import LLMSettings


class LLMFactory:
    """Factory for creating ChatOpenAI instances with session-specific configurations"""
    
    # Default configurations
    DEFAULT_STREAMING_CONFIG = {
        "temperature": 0.1,
        "streaming": True,
        "max_tokens": 2000
    }
    
    DEFAULT_ANALYSIS_CONFIG = {
        "temperature": 0,
        "streaming": False,
        "seed": 42,  # Consistent analysis results
        "max_tokens": 2000,
        "timeout": 60
    }
    
    @staticmethod
    def create_streaming_llm(llm_settings: LLMSettings, **kwargs) -> ChatOpenAI:
        """
        Create a ChatOpenAI instance for streaming conversations (Anisa chat)
        
        Args:
            llm_settings: LLMSettings instance containing API key and model config
            **kwargs: Additional configuration overrides
            
        Returns:
            ChatOpenAI instance configured for streaming
        """
        config = LLMFactory.DEFAULT_STREAMING_CONFIG.copy()
        config.update(kwargs)
        
        return ChatOpenAI(
            api_key=llm_settings.get_api_key(),
            model=llm_settings.chat_model,  # e.g. gpt-4o
            **config
        )
    
    @staticmethod
    def create_analysis_agent(llm_settings: LLMSettings, **kwargs) -> ChatOpenAI:
        """
        Create a ChatOpenAI instance for analysis tasks (depression assessment)
        
        Args:
            llm_settings: LLMSettings instance containing API key and model config  
            **kwargs: Additional configuration overrides
            
        Returns:
            ChatOpenAI instance configured for consistent analysis
        """
        config = LLMFactory.DEFAULT_ANALYSIS_CONFIG.copy()
        config.update(kwargs)
        
        return ChatOpenAI(
            api_key=llm_settings.get_api_key(),
            model=llm_settings.analysis_model,  # e.g. gpt-4o-mini
            **config
        )
    
    @staticmethod
    def validate_settings(llm_settings: LLMSettings) -> Dict[str, Any]:
        """
        Validate LLM settings before creating instances
        
        Args:
            llm_settings: LLMSettings to validate
            
        Returns:
            Dict with validation results
        """
        issues = []
        
        # Check API key
        decrypted_key = llm_settings.get_api_key()
        if not decrypted_key:
            issues.append("Missing OpenAI API key")
        elif len(decrypted_key) < 20:
            issues.append("Invalid OpenAI API key format")
        
        # Check models
        if not llm_settings.chat_model:
            issues.append("Missing chat model configuration")
        
        if not llm_settings.analysis_model:
            issues.append("Missing analysis model configuration")
        
        # Check depression aspects
        if not llm_settings.depression_aspects:
            issues.append("Missing depression aspects configuration")
        elif not isinstance(llm_settings.depression_aspects, dict):
            issues.append("Invalid depression aspects format")
        elif not llm_settings.depression_aspects.get('aspects'):
            issues.append("Empty depression aspects list")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }
    
    @staticmethod
    def test_connection(llm_settings: LLMSettings, model_type: str = "chat") -> Dict[str, Any]:
        """
        Test connection to OpenAI API with given settings
        
        Args:
            llm_settings: LLMSettings to test
            model_type: "chat" or "analysis" - which model to test
            
        Returns:
            Dict with test results
        """
        try:
            if model_type == "chat":
                llm = LLMFactory.create_streaming_llm(llm_settings, streaming=False)
                model_name = llm_settings.chat_model
            else:
                llm = LLMFactory.create_analysis_agent(llm_settings)
                model_name = llm_settings.analysis_model
            
            # Simple test message
            test_response = llm.invoke([
                {"role": "user", "content": "Test connection. Respond with 'OK'."}
            ])
            
            return {
                "success": True,
                "model": model_name,
                "response_length": len(test_response.content),
                "message": f"Connection successful for {model_name}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "model": model_name if 'model_name' in locals() else "unknown",
                "error": str(e),
                "message": f"Connection failed: {str(e)}"
            }
    
    @staticmethod
    def create_custom_llm(
        api_key: str,
        model: str,
        temperature: float = 0.7,
        streaming: bool = False,
        **kwargs
    ) -> ChatOpenAI:
        """
        Create a ChatOpenAI instance with custom configuration
        
        Args:
            api_key: OpenAI API key
            model: Model name (e.g. gpt-4o)
            temperature: Temperature for generation
            streaming: Whether to enable streaming
            **kwargs: Additional ChatOpenAI parameters
            
        Returns:
            ChatOpenAI instance
        """
        return ChatOpenAI(
            api_key=api_key,
            model=model,
            temperature=temperature,
            streaming=streaming,
            **kwargs
        )
    
    @staticmethod
    def get_model_info(llm_settings: LLMSettings) -> Dict[str, Any]:
        """
        Get information about the models configured in LLM settings
        
        Args:
            llm_settings: LLMSettings instance
            
        Returns:
            Dict with model information
        """
        return {
            "chat_model": {
                "name": llm_settings.chat_model,
                "purpose": "Streaming conversation (Anisa)",
                "temperature": LLMFactory.DEFAULT_STREAMING_CONFIG["temperature"],
                "streaming": True
            },
            "analysis_model": {
                "name": llm_settings.analysis_model,
                "purpose": "Depression analysis",
                "temperature": LLMFactory.DEFAULT_ANALYSIS_CONFIG["temperature"],
                "streaming": False,
                "seed": LLMFactory.DEFAULT_ANALYSIS_CONFIG["seed"]
            },
            "depression_aspects_count": len(llm_settings.depression_aspects.get('aspects', [])),
            "settings_id": llm_settings.id,
            "is_default": llm_settings.is_default
        }


class LLMConfigurationError(Exception):
    """Exception raised when LLM configuration is invalid"""
    pass


class LLMConnectionError(Exception):
    """Exception raised when LLM connection fails"""
    pass