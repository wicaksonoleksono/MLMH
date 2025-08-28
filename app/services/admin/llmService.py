# app/services/admin/llmService.py
import os
from typing import List, Optional, Dict, Any
from flask import current_app
from sqlalchemy import and_
import requests
from ...model.admin.llm import LLMSettings
from ...db import get_session


class LLMService:
    """LLM service for managing LLM settings and OpenAI integration"""
    
    # Default depression aspects with name and description
    DEFAULT_ASPECTS = [
        {"name": "Anhedonia", "description": "kehilangan minat/kenikmatan"},
        {"name": "Bias kognitif negatif", "description": "hopelessness & negative thinking patterns"},
        {"name": "Rumination", "description": "pikiran berputar tanpa solusi"},
        {"name": "Psikomotor retardation", "description": "perlambatan gerakan dan bicara"},
        {"name": "Gangguan tidur", "description": "insomnia, kualitas tidur jelek"},
        {"name": "Iritabilitas", "description": "ledakan marah & mudah tersinggung"},
        {"name": "Rasa bersalah berlebih", "description": "self-blame & worthlessness"},
        {"name": "Gangguan kognitif", "description": "concentration & executive function issues"},
        {"name": "Penarikan diri sosial", "description": "isolasi & withdrawal"},
        {"name": "Alexithymia", "description": "sulit mengenali & mengungkap emosi"},
        {"name": "Defisit regulasi emosi", "description": "kesulitan mengatur emosi"}
    ]


    
    # Hard-coded Anisa system prompt - TIDAK BISA DIUBAH
    ANISA_SYSTEM_PROMPT = """Anda adalah Anisa, seorang mahasiswa psikologi yang supportive dan senang hati mendengarkan curhatan orang lain. Teman anda kemungkinan mengalami gejala depresi, atau bisa jadi tidak.

Buatlah beberapa pertanyaan dengan gaya non formal kepada rekan anda tentang aktivitas sehari-hari atau tentang kejadian yang akhir-akhir ini dialami. Tindak lanjuti setiap jawaban dengan pertanyaan yang lebih dalam. Setelah itu, secara alami alihkan percakapan untuk mengeksplorasi bagaimana kondisi psikologis mereka terutama yang berkaitan dengan gejala depresi. Berikut adalah indikator-indikator dari gejala depresi:

{aspects}

Pastikan kamu menggali secara dalam, rinci, friendly, dan subtle.
Silahkan sapa dahulu sebelum memulai percakapan eksploratif.

Nanti jika sudah didapatkan semua informasi yang perlu didapatkan Tolong stop ya dengan menutup. Percakapan dengan "gak papa kamu pasti bisa kok, semangat yaa ! Kalau memang darurat deh Hubungi psikolog terdekat mu !!" Tidak perlu bilang secara eksplisit menyebutkan mengenai depresi atau sejenisnya. Kemudian tulis </end_conversation> pada akhir kalimat"""

    @staticmethod
    def get_settings() -> List[Dict[str, Any]]:
        """Get all LLM settings"""
        with get_session() as db:
            settings = db.query(LLMSettings).filter(LLMSettings.is_active == True).all()
            
            return [{
                'id': setting.id,
                'setting_name': setting.setting_name,
                'instructions': setting.instructions,
                'openai_api_key': setting.openai_api_key,  # Return full API key for editing
                'chat_model': setting.chat_model,
                'analysis_model': setting.analysis_model,
                'depression_aspects': setting.depression_aspects,
                'is_default': setting.is_default
            } for setting in settings]

    @staticmethod
    def create_settings(openai_api_key: str, chat_model: str = "gpt-4o", 
                       analysis_model: str = "gpt-4o-mini",
                       depression_aspects: Optional[List[str]] = None,
                       instructions: str = None,
                       is_default: bool = False) -> Dict[str, Any]:
        """Create or update LLM settings - no streaming validation"""
        with get_session() as db:
            
            # Auto-generate setting name
            setting_name = f"LLM Settings (Chat: {chat_model}, Analysis: {analysis_model})"
            
            # Null handling for depression_aspects - don't save if null/empty
            aspects_json = None
            if depression_aspects is not None and len(depression_aspects) > 0:
                # Format aspect names: spaces to underscores, lowercase
                for aspect in depression_aspects:
                    aspect["name"] = aspect["name"].replace(" ", "_").lower()
                # Store aspects as JSON
                aspects_json = {"aspects": depression_aspects}
            
            # Null handling for instructions - don't save if null/empty
            final_instructions = instructions if instructions and instructions.strip() else None
            
            # Look for existing settings (assume only one set of settings for now)
            existing = db.query(LLMSettings).filter(LLMSettings.is_active == True).first()
            
            if is_default:
                # Remove default from other settings
                db.query(LLMSettings).filter(LLMSettings.is_default == True).update({'is_default': False})
            
            if existing:
                # Store old settings ID for active session refresh
                old_settings_id = existing.id
                
                # Update existing settings
                existing.setting_name = setting_name
                existing.instructions = final_instructions
                existing.openai_api_key = openai_api_key
                existing.chat_model = chat_model
                existing.analysis_model = analysis_model
                existing.depression_aspects = aspects_json
                existing.is_default = is_default
                existing.is_active = True
                settings = existing
                
                # Trigger refresh for active sessions using these settings
                try:
                    refresh_result = LLMService.trigger_active_sessions_refresh(old_settings_id)
                    print(f"Refreshed {refresh_result.get('total_sessions', 0)} active sessions")
                except Exception as e:
                    print(f"Warning: Failed to refresh active sessions: {e}")
                    
            else:
                # Create new settings
                settings = LLMSettings(
                    setting_name=setting_name,
                    instructions=final_instructions,
                    openai_api_key=openai_api_key,
                    chat_model=chat_model,
                    analysis_model=analysis_model,
                    depression_aspects=aspects_json,
                    is_default=is_default,
                    is_active=True
                )
                db.add(settings)
            
            db.commit()
            
            return {
                "status": "OLKORECT",
                'id': settings.id,
                'setting_name': settings.setting_name,
                'instructions': settings.instructions or '',
                'openai_api_key': openai_api_key or '',  # Always return string, even if empty
                'chat_model': settings.chat_model,
                'analysis_model': settings.analysis_model,
                'depression_aspects': settings.depression_aspects,
                'is_default': settings.is_default,
                'streaming_compatible': True
            }

    @staticmethod
    def update_settings(settings_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update LLM settings"""
        with get_session() as db:
            settings = db.query(LLMSettings).filter(
                and_(LLMSettings.id == settings_id, LLMSettings.is_active == True)
            ).first()

            if not settings:
                raise ValueError(f"LLM settings with ID {settings_id} not found")

            if updates.get('is_default'):
                # Remove default from other settings
                db.query(LLMSettings).filter(LLMSettings.is_default == True).update({'is_default': False})

            for key, value in updates.items():
                if hasattr(settings, key):
                    # Null handling for depression_aspects
                    if key == 'depression_aspects':
                        if value is None or (isinstance(value, dict) and not value.get('aspects')):
                            setattr(settings, key, None)
                        elif isinstance(value, dict) and 'aspects' in value:
                            # Format aspect names: spaces to underscores, lowercase
                            for aspect in value['aspects']:
                                aspect["name"] = aspect["name"].replace(" ", "_").lower()
                            setattr(settings, key, value)
                    # Null handling for instructions
                    elif key == 'instructions':
                        final_value = value if value and value.strip() else None
                        setattr(settings, key, final_value)
                    else:
                        setattr(settings, key, value)

            db.commit()

            return {
                'id': settings.id,
                'setting_name': settings.setting_name,
                'chat_model': settings.chat_model,
                'analysis_model': settings.analysis_model
            }

    @staticmethod
    def delete_settings(settings_id: int) -> Dict[str, Any]:
        """Soft delete LLM settings"""
        with get_session() as db:
            settings = db.query(LLMSettings).filter(LLMSettings.id == settings_id).first()

            if not settings:
                raise ValueError(f"LLM settings with ID {settings_id} not found")

            settings.is_active = False
            db.commit()

            return {'id': settings_id, 'deleted': True}

    @staticmethod
    def get_default_settings() -> Dict[str, Any]:
        """Get hardcoded default LLM settings for 'Muat Default' button"""
        return {
            "setting_name": "Default LLM Settings",
            "instructions": "",
            "openai_api_key": "",
            "chat_model": "gpt-4o",
            "analysis_model": "gpt-4o-mini",
            "depression_aspects": {"aspects": LLMService.DEFAULT_ASPECTS},
            "is_default": True
        }

    @staticmethod
    def build_system_prompt(aspects: List[dict]) -> str:
        """Build final system prompt by combining hard-coded template with aspects"""
        aspects_text = "\n".join(f"- {aspect['name']}: {aspect['description']}" for aspect in aspects)
        return LLMService.ANISA_SYSTEM_PROMPT.format(aspects=aspects_text)
    
    @staticmethod
    def build_analysis_prompt(aspects: List[dict]) -> str:
        """Build analysis prompt for depression assessment"""
        key_aspects = "\n".join(f"{aspect['name']}: {aspect['description']}" for aspect in aspects)
        
        return f"""Berdasarkan indikator-indikator dari gejala depresi berikut:
{key_aspects}

Buatlah analisa jawaban "Teman" diatas untuk setiap indikator tersebut beserta penilaian skala angka (0-3) yang diberikan untuk menunjukkan sejauh mana indikasi gejala tersebut muncul dalam percakapan:
0: Tidak Ada Indikasi Jelas (Gejala tidak muncul dalam percakapan)
1: Indikasi Ringan (Gejala tersirat atau disebutkan secara tidak langsung)
2: Indikasi Sedang (Gejala disebutkan dengan cukup jelas, namun tidak mendominasi)
3: Indikasi Kuat (Gejala disebutkan secara eksplisit, berulang, dan menjadi keluhan utama)

Format output JSON:
{{
  "indicator_name": {{
    "explanation": "penjelasan detail",
    "indicator_score": 0-3
  }}
}}"""

    @staticmethod
    def get_available_models(api_key: str = None) -> List[str]:
        """Get available OpenAI models from API"""
        if api_key is None:
            # Try to get API key from current settings first, then config
            with get_session() as db:
                settings = db.query(LLMSettings).filter(LLMSettings.is_active == True).first()
                if settings:
                    api_key = settings.openai_api_key
            
            # Fallback to config if no settings
            if not api_key:
                api_key = current_app.config.get('OPENAI_API_KEY')
        
        if not api_key:
            return []
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            
            # Get all models using OpenAI client
            models_response = client.models.list()
            models = [model.id for model in models_response.data]
            
            # Filter for chat models (exclude embeddings, tts, etc)
            chat_models = [m for m in models if any(prefix in m for prefix in ['gpt-', 'o1-', 'o3-'])]
            
            return sorted(chat_models)
            
        except Exception as e:
            print(f"Error fetching OpenAI models: {e}")
            return []

    @staticmethod
    def test_api_key(api_key: str) -> bool:
        """Test if OpenAI API key is valid - simple and cheap"""
        if not api_key or not api_key.strip():
            return False
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            # Simple models list call - cheap and reliable
            models = client.models.list()
            return True
            
        except Exception as e:
            print(f"Error testing API key: {e}")
            return False

    @staticmethod
    def test_model_availability(model_id: str, api_key: str = None) -> bool:
        """Test if a specific model is available"""
        if api_key is None:
            # Try to get API key from current settings first, then config
            with get_session() as db:
                settings = db.query(LLMSettings).filter(LLMSettings.is_active == True).first()
                if settings:
                    api_key = settings.openai_api_key
            
            # Fallback to config if no settings
            if not api_key:
                api_key = current_app.config.get('OPENAI_API_KEY')
        
        if not api_key or not model_id:
            return False
        
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            # Test with a minimal completion request
            payload = {
                'model': model_id,
                'messages': [{'role': 'user', 'content': 'test'}],
                'max_tokens': 1
            }
            
            response = requests.post(
                'https://api.openai.com/v1/chat/completions', 
                headers=headers, 
                json=payload, 
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"Error testing model {model_id}: {e}")
            return False

    @staticmethod
    def test_streaming_compatibility(llm_settings_id: int) -> Dict[str, Any]:
        """Test if LLM settings are compatible with streaming architecture"""
        with get_session() as db:
            settings = db.query(LLMSettings).filter_by(id=llm_settings_id).first()
            if not settings:
                return {"compatible": False, "error": "Settings not found"}
        
        try:
            # Import our streaming factory to test compatibility
            from ..llm.factory import LLMFactory
            
            # Test factory validation
            validation = LLMFactory.validate_settings(settings)
            if not validation["valid"]:
                return {
                    "compatible": False,
                    "error": "Settings validation failed",
                    "issues": validation["issues"]
                }
            
            # Test creating streaming LLM
            streaming_test = LLMFactory.test_connection(settings, "chat")
            analysis_test = LLMFactory.test_connection(settings, "analysis")
            
            return {
                "compatible": streaming_test["success"] and analysis_test["success"],
                "streaming_llm": streaming_test,
                "analysis_agent": analysis_test,
                "depression_aspects_count": len(settings.depression_aspects.get('aspects', [])),
                "models": {
                    "chat_model": settings.chat_model,
                    "analysis_model": settings.analysis_model
                }
            }
            
        except Exception as e:
            return {
                "compatible": False,
                "error": f"Compatibility test failed: {str(e)}"
            }

    @staticmethod
    def trigger_active_sessions_refresh(llm_settings_id: int) -> Dict[str, Any]:
        """Trigger settings refresh for all active sessions using these LLM settings"""
        try:
            from ..llm.manager import GlobalSessionManager
            from ...model.assessment.sessions import AssessmentSession
            
            refresh_results = []
            
            with get_session() as db:
                # Find all active sessions using these LLM settings
                active_sessions = db.query(AssessmentSession).filter(
                    AssessmentSession.llm_settings_id == llm_settings_id,
                    AssessmentSession.status.in_(['STARTED', 'CONSENT', 'PHQ_COMPLETED'])
                ).all()
                
                for session in active_sessions:
                    refreshed = GlobalSessionManager.force_settings_refresh(session.id)
                    refresh_results.append({
                        "session_id": session.id,
                        "refreshed": refreshed
                    })
            
            return {
                "success": True,
                "refreshed_sessions": refresh_results,
                "total_sessions": len(refresh_results),
                "message": f"Refreshed {len(refresh_results)} active sessions"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to refresh active sessions: {str(e)}"
            }
    
    @staticmethod
    def get_streaming_status() -> Dict[str, Any]:
        """Get status of streaming architecture and active conversations"""
        try:
            from ..llm.manager import GlobalSessionManager
            
            stats = GlobalSessionManager.get_stats()
            active_sessions = GlobalSessionManager.get_active_sessions()
            
            return {
                "streaming_enabled": True,
                "statistics": stats,
                "active_conversations": active_sessions,
                "total_managers": len(active_sessions)
            }
            
        except Exception as e:
            return {
                "streaming_enabled": False,
                "error": str(e),
                "message": f"Streaming status unavailable: {str(e)}"
            }

    @staticmethod
    def validate_streaming_models(chat_model: str, analysis_model: str, api_key: str) -> Dict[str, Any]:
        """DISABLED - Streaming validation no longer used"""
        return {
            "chat_model_valid": True,
            "analysis_model_valid": True,
            "streaming_compatible": True,
            "issues": []
        }
    
    @staticmethod
    def test_langchain_integration(llm_settings_id: int) -> Dict[str, Any]:
        """Test LangChain integration with the streaming architecture"""
        with get_session() as db:
            settings = db.query(LLMSettings).filter_by(id=llm_settings_id).first()
            if not settings:
                return {"success": False, "error": "Settings not found"}
        
        try:
            from ..llm.factory import LLMFactory
            from langchain_core.messages import HumanMessage
            
            # Test streaming LLM creation and basic functionality
            streaming_llm = LLMFactory.create_streaming_llm(settings)
            analysis_agent = LLMFactory.create_analysis_agent(settings)
            
            # Test simple message with streaming LLM
            test_message = [HumanMessage(content="Hello, this is a test message. Respond briefly.")]
            
            try:
                streaming_response = streaming_llm.invoke(test_message)
                streaming_success = bool(streaming_response.content)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Streaming LLM test failed: {str(e)}",
                    "component": "streaming_llm"
                }
            
            # Test analysis agent
            try:
                analysis_response = analysis_agent.invoke(test_message)
                analysis_success = bool(analysis_response.content)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Analysis agent test failed: {str(e)}",
                    "component": "analysis_agent"
                }
            
            # Test streaming capability
            streaming_chunks = []
            try:
                for chunk in streaming_llm.stream(test_message):
                    if chunk.content:
                        streaming_chunks.append(chunk.content)
                        if len(streaming_chunks) >= 3:  # Just test first few chunks
                            break
                
                streaming_works = len(streaming_chunks) > 0
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Streaming test failed: {str(e)}",
                    "component": "streaming"
                }
            
            return {
                "success": True,
                "streaming_llm_working": streaming_success,
                "analysis_agent_working": analysis_success,
                "streaming_capability": streaming_works,
                "streaming_chunks_received": len(streaming_chunks),
                "models_tested": {
                    "chat_model": settings.chat_model,
                    "analysis_model": settings.analysis_model
                },
                "langchain_version": "compatible",
                "message": "LangChain integration test successful"
            }
            
        except ImportError as e:
            return {
                "success": False,
                "error": f"LangChain import failed: {str(e)}",
                "message": "LangChain dependencies may not be installed"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"LangChain integration test failed: {str(e)}",
                "message": "Unexpected error during integration test"
            }