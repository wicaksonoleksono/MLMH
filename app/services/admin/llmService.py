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

    # Default analysis scale (shared across all aspects)
    DEFAULT_ANALYSIS_SCALE = [
        {"value": 0, "description": "Tidak Ada Indikasi Jelas (Gejala tidak muncul dalam percakapan)"},
        {"value": 1, "description": "Indikasi Ringan (Gejala tersirat atau disebutkan secara tidak langsung)"},
        {"value": 2, "description": "Indikasi Sedang (Gejala disebutkan dengan cukup jelas, namun tidak mendominasi)"},
        {"value": 3, "description": "Indikasi Kuat (Gejala disebutkan secara eksplisit, berulang, dan menjadi keluhan utama)"}
    ]


    
    # Hard-coded Anisa system prompt - TIDAK BISA DIUBAH
    ANISA_SYSTEM_PROMPT = """
    Anda adalah Anisa, seorang mahasiswa psikologi yang supportive dan senang hati mendengarkan curhatan orang lain.
    Salah satu teman Anda kemungkinan mengalami gejala depresi, atau bisa jadi tidak. Buatlah beberapa pertanyaan dengan
    gaya non-formal kepada rekan Anda tentang aktivitas yang dilakukan **2 pekan terakhir**, 
    yang kemudian akan menyangkut dengan aspek-aspek di bawah ini:
    {aspects}

    Satu pertanyaan per pesan. Tindak lanjuti setiap jawaban dengan 1–2 pertanyaan yang lebih dalam (contoh konkret, frekuensi, durasi, dampak ke aktivitas/tidur/energi/relasi, perubahan dibanding biasanya).
    Jika nada jawaban relatif negatif/berat, validasi dulu secara hangat agar pengguna tetap merasa nyaman, lalu lanjut pelan dan jelas.
    Setelah itu, secara alami alihkan percakapan untuk mengeksplorasi bagaimana kondisi psikologis mereka, terutama yang berkaitan dengan aspek-aspek diatas. 
    Berikut adalah indikator-indikator dari gejala depresi: gunakan saat relevan—tanpa memberi label/diagnosis.
    Tolong eksplorasi peggguna berdasarkan aspek, ketahui informasinya secara detil. Pastikan seluruh Aspek telah 
    Terpenuhi. 
    Silakan sapa terlebih dahulu sebelum memulai percakapan eksploratif, dan tutup dengan ringkasan singkat lalu
     jika sudah didapatkan semua informasi yang perlu didapatkan Tolong stop ya dengan menutup  
    Percakapan dengan "gak papa kamu pasti bisa kok, semangat yaa ! 
    Kalau memang darurat deh Hubungi psikolog terdekat mu !!" 
    Tidak perlu bilang secara eksplisit menyebutkan mengenai depresi atau sejenisnya. 
    Kemudian tulis </end_conversation> pada akhir kalimat ini untuk parser output.
    
    """

    @staticmethod
    def get_settings() -> List[Dict[str, Any]]:
        """Get all LLM settings"""
        with get_session() as db:
            settings = db.query(LLMSettings).filter(LLMSettings.is_active == True).all()
            
            
            return [{
                'id': setting.id,
                'instructions': setting.instructions,
                'openai_api_key': setting.get_masked_api_key(),  # Return masked API key for security
                'openai_api_key_unmasked': setting.get_api_key(),  # Return unmasked API key for frontend use
                'chat_model': setting.chat_model,
                'analysis_model': setting.analysis_model,
                'depression_aspects': setting.depression_aspects.get('aspects', []) if setting.depression_aspects else [],
                'analysis_scale': setting.analysis_scale.get('scale', []) if setting.analysis_scale else [],
                'is_default': setting.is_default
            } for setting in settings]

    @staticmethod
    def create_settings(openai_api_key: Optional[str] = None, chat_model: str = "gpt-4o", 
                       analysis_model: str = "gpt-4o-mini",
                       depression_aspects: Optional[List[Dict]] = None,
                       analysis_scale: Optional[List[Dict]] = None,
                       instructions: str = None,
                       is_default: bool = False) -> Dict[str, Any]:
        """Create or update LLM settings - no streaming validation"""
        with get_session() as db:
            
            # No longer using setting_name field
            
            # Null handling for depression_aspects - don't save if null/empty
            aspects_json = None
            if depression_aspects is not None and len(depression_aspects) > 0:
                # Format aspect names: spaces to underscores, lowercase
                for aspect in depression_aspects:
                    aspect["name"] = aspect["name"].replace(" ", "_").lower()
                # Store aspects as JSON
                aspects_json = {"aspects": depression_aspects}
            
            # Handle analysis_scale separately  
            scale_json = None
            if analysis_scale is not None and len(analysis_scale) > 0:
                scale_json = {"scale": analysis_scale}
            
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
                existing.instructions = final_instructions
                if openai_api_key is not None:  # Only update if new API key provided
                    existing.set_api_key(openai_api_key)  # Use encryption method
                existing.chat_model = chat_model
                existing.analysis_model = analysis_model
                existing.depression_aspects = aspects_json
                existing.analysis_scale = scale_json
                existing.is_default = is_default
                
                # Set is_active based on field completeness (API key NOT required)
                aspects_valid = (aspects_json and 
                               isinstance(aspects_json, dict) and
                               aspects_json.get('aspects') and
                               len(aspects_json.get('aspects', [])) > 0)
                models_valid = (chat_model and chat_model.strip() != '' and
                               analysis_model and analysis_model.strip() != '')
                is_active_value = aspects_valid and models_valid  # API key not required for is_active
                # Ensure is_active is never None
                existing.is_active = bool(is_active_value)
                
                settings = existing
                
                # Note: Active sessions will use new settings on next request
                
            else:
                # Create new settings
                settings = LLMSettings(
                    instructions=final_instructions,
                    chat_model=chat_model,
                    analysis_model=analysis_model,
                    depression_aspects=aspects_json,
                    analysis_scale=scale_json,
                    is_default=is_default
                )
                if openai_api_key is not None:  # Only set if API key provided
                    settings.set_api_key(openai_api_key)  # Use encryption method
                else:
                    settings.openai_api_key = ""  # Empty encrypted key
                
                # Set is_active based on field completeness (API key NOT required)
                aspects_valid = (aspects_json and 
                               isinstance(aspects_json, dict) and
                               aspects_json.get('aspects') and
                               len(aspects_json.get('aspects', [])) > 0)
                models_valid = (chat_model and chat_model.strip() != '' and
                               analysis_model and analysis_model.strip() != '')
                is_active_value = aspects_valid and models_valid  # API key not required for is_active
                # Ensure is_active is never None
                settings.is_active = bool(is_active_value)
                
                db.add(settings)
            
            db.commit()
            
            return {
                "status": "OLKORECT",
                'id': settings.id,
                'instructions': settings.instructions or '',
                'openai_api_key': openai_api_key or '',  # Always return string, even if empty
                'chat_model': settings.chat_model,
                'analysis_model': settings.analysis_model,
                'depression_aspects': settings.depression_aspects.get('aspects', []) if settings.depression_aspects else [],
                'is_default': settings.is_default,
                'streaming_compatible': True
            }

    @staticmethod
    def update_settings(settings_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update LLM settings"""
        #  DEBUG: Log what frontend is sending
        print(f" DEBUG update_settings received: {updates}")
        for key, value in updates.items():
            print(f"  {key}: {type(value).__name__} = {value}")
        
        #  DETECT FIELD MAPPING BUG: is_active should never be None or dict
        if 'is_active' in updates:
            if updates['is_active'] is None:
                print(f" BUG DETECTED: is_active is None! Frontend is sending wrong field mapping.")
                print(f"   is_active value: {updates['is_active']}")
                del updates['is_active']
                print(f"   Removed is_active from updates to prevent crash.")
            elif isinstance(updates['is_active'], dict):
                print(f" BUG DETECTED: is_active is a dict! Frontend is sending wrong field mapping.")
                print(f"   is_active value: {updates['is_active']}")
                del updates['is_active']
                print(f"   Removed is_active from updates to prevent crash.")
        
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
                if hasattr(settings, key) and key != 'is_active':  # Skip is_active field, it's auto-calculated
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
            
            # Recalculate is_active based on field completeness (API key NOT required)
            aspects_valid = (settings.depression_aspects and 
                           isinstance(settings.depression_aspects, dict) and
                           settings.depression_aspects.get('aspects') and
                           len(settings.depression_aspects.get('aspects', [])) > 0)
            models_valid = (settings.chat_model and settings.chat_model.strip() != '' and
                           settings.analysis_model and settings.analysis_model.strip() != '')
            settings.is_active = aspects_valid and models_valid  # API key not required for is_active

            db.commit()

            return {
                'id': settings.id,
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

            db.commit()

            return {'id': settings_id, 'deleted': True}

    @staticmethod
    def get_default_settings() -> Dict[str, Any]:
        """Get hardcoded default LLM settings for 'Muat Default' button"""
        return {
            "instructions": "",
            "openai_api_key": "",
            "chat_model": "gpt-4o",
            "analysis_model": "gpt-4o-mini",
            "depression_aspects": LLMService.DEFAULT_ASPECTS,
            "analysis_scale": LLMService.DEFAULT_ANALYSIS_SCALE,
            "is_default": True
        }

    @staticmethod
    def build_system_prompt(aspects: List[dict]) -> str:
        """Build final system prompt by combining hard-coded template with aspects"""
        aspects_text = "\n".join(f"- {aspect['name']}: {aspect['description']}" for aspect in aspects)
        return LLMService.ANISA_SYSTEM_PROMPT.format(aspects=aspects_text)
    

    @staticmethod
    def get_available_models(api_key: str = None) -> List[str]:
        # INI PENTING .. 
        """Get available OpenAI models from API"""
        if api_key is None:
            # Try to get API key from current settings first, then config
            with get_session() as db:
                settings = db.query(LLMSettings).filter(LLMSettings.is_active == True).first()
                if settings:
                    # Use get_api_key() to decrypt the key properly
                    api_key = settings.get_api_key()
            
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
            # langsung lihat 
            models = [model.id for model in models_response.data]
            
            # Filter for chat models (exclude embeddings, tts, etc)
            chat_models = [m for m in models if any(prefix in m for prefix in ['gpt-', 'o1-', 'o3-'] or not 'gpt-5')]
            
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
            models = client.models.list()
            return True
            
        except Exception as e:
            print(f"Error testing API key: {e}")
            return False

    @staticmethod
    def test_model_availability(model_id: str, api_key: str = None) -> bool:
        """Test if a specific model is available"""
        if api_key is None:
            with get_session() as db:
                settings = db.query(LLMSettings).filter(LLMSettings.is_active == True).first()
                if settings:
                    api_key = settings.get_api_key()
            if not api_key:
                api_key = current_app.config.get('OPENAI_API_KEY')
        
        if not api_key or not model_id:
            return False
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            payload = {
                'model': model_id,
                'messages': [{'role': 'user', 'content': 'test'}],
                'max_tokens': 1
            }
            response = requests.post(
                'https://api.openai.com/v1/chat/completions', 
                headers=headers, 
                json=payload, 
                timeout=None
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error testing model {model_id}: {e}")
            return False

