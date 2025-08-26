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
        """Create or update LLM settings"""
        with get_session() as db:
            # Auto-generate setting name
            setting_name = f"LLM Settings (Chat: {chat_model}, Analysis: {analysis_model})"
            
            # Use defaults if not provided
            if depression_aspects is None:
                depression_aspects = LLMService.DEFAULT_ASPECTS
            
            # Store aspects as JSON
            aspects_json = {"aspects": depression_aspects}
            
            # Look for existing settings (assume only one set of settings for now)
            existing = db.query(LLMSettings).filter(LLMSettings.is_active == True).first()
            
            if is_default:
                # Remove default from other settings
                db.query(LLMSettings).filter(LLMSettings.is_default == True).update({'is_default': False})
            
            if existing:
                # Update existing settings
                existing.setting_name = setting_name
                existing.instructions = instructions
                existing.openai_api_key = openai_api_key
                existing.chat_model = chat_model
                existing.analysis_model = analysis_model
                existing.depression_aspects = aspects_json
                existing.is_default = is_default
                existing.is_active = True
                settings = existing
            else:
                # Create new settings
                settings = LLMSettings(
                    setting_name=setting_name,
                    instructions=instructions,
                    openai_api_key=openai_api_key,
                    chat_model=chat_model,
                    analysis_model=analysis_model,
                    depression_aspects=aspects_json,
                    is_default=is_default
                )
                db.add(settings)
            
            db.commit()
            
            return {
                'id': settings.id,
                'setting_name': settings.setting_name,
                'instructions': settings.instructions,
                'openai_api_key': openai_api_key,  # Return full key for immediate use
                'chat_model': settings.chat_model,
                'analysis_model': settings.analysis_model,
                'depression_aspects': settings.depression_aspects,
                'is_default': settings.is_default
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
    def get_default_settings() -> Optional[Dict[str, Any]]:
        """Get default LLM settings"""
        with get_session() as db:
            settings = db.query(LLMSettings).filter(
                and_(LLMSettings.is_default == True, LLMSettings.is_active == True)
            ).first()

            if settings:
                return {
                    'id': settings.id,
                    'setting_name': settings.setting_name,
                    'instructions': settings.instructions,
                    'openai_api_key': settings.openai_api_key,
                    'chat_model': settings.chat_model,
                    'analysis_model': settings.analysis_model,
                    'depression_aspects': settings.depression_aspects,
                    'is_default': settings.is_default
                }
            return None

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
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get('https://api.openai.com/v1/models', headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            models = [model['id'] for model in data.get('data', [])]
            
            # Filter for chat models (exclude embeddings, tts, etc)
            chat_models = [m for m in models if any(prefix in m for prefix in ['gpt-', 'o1-', 'o3-'])]
            
            return sorted(chat_models)
            
        except Exception as e:
            print(f"Error fetching OpenAI models: {e}")
            return []

    @staticmethod
    def test_api_key(api_key: str) -> bool:
        """Test if OpenAI API key is valid"""
        if not api_key:
            return False
        
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            # Simple test request to models endpoint
            response = requests.get('https://api.openai.com/v1/models', headers=headers, timeout=10)
            return response.status_code == 200
            
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