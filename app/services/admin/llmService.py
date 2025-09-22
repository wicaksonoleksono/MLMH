# app/services/admin/llmService.py
import os
from typing import List, Optional, Dict, Any
from flask import current_app
from sqlalchemy import and_
import requests
from ...model.admin.llm import LLMSettings
from ...db import get_session

import time
import hashlib
import hmac

class LLMService:
    """LLM service for managing LLM settings and OpenAI integration"""
            # {"name": "Alexithymia", "description": "Apakah pengguna mengalami kesulitan mengenali dan mengungkapkan emosi mereka?"},
        # {"name": "Defisit Regulasi Emosi", "description": "Apakah pengguna kesulitan dalam mengatur dan mengelola emosi mereka?"}
    # Default depression aspects with name and description
    DEFAULT_ASPECTS = [
         {
            "name": "Anhedonia atau Kehilangan Minat atau Kesenangan",
            "description": "Pengguna kehilangan minat atau kesenangan dalam hampir semua aktivitas sehari-hari. Jika kegiatan yang dulu bikin semangat sekarang terasa hambar, menurutmu apa yang bikin rasanya berubah?"
        },
        {
            "name": "Mood Depresi",
            "description": "Pengguna mengalami suasana hati yang tertekan hampir sepanjang hari, hampir setiap hari. Kalau belakangan ini terasa sedih terus, menurutmu apa yang biasanya memicu atau memperberat perasaan itu?"
        },
       
        {
            "name": "Perubahan Berat Badan atau Nafsu Makan",
            "description": "Pengguna mengalami penurunan atau peningkatan berat badan yang signifikan, atau perubahan nafsu makan. Kalau pola makanmu berubah, apa yang biasanya mempengaruhi—stres, ritme harian, atau hal lain?"
        },
        {
            "name": "Gangguan Tidur",
            "description": "Pengguna mengalami insomnia atau hipersomnia hampir setiap hari. Saat tidur berantakan, apa yang biasanya membuatmu susah/lelap—pikiran tertentu, jadwal, atau kebiasaan sebelum tidur?"
        },
        {
            "name": "Retardasi atau Agitasi Psikomotor",
            "description": "Pengguna menunjukkan perlambatan gerakan/pembicaraan atau agitasi yang dapat diamati oleh orang lain. Tanyakan pada teman apakah mereka melihat kamu lebih lambat atau lebih gelisah dari biasanya; menurutmu apa yang memicu perubahan ritme itu?"
        },
        {
            "name": "Kelelahan atau Kehilangan Energi",
            "description": "Pengguna merasa lelah atau kehilangan energi hampir setiap hari. Saat energi cepat turun, biasanya apa yang terjadi sebelumnya—kurang tidur, beban pikiran, atau pola kerja?"
        },
        {
            "name": "Perasaan Tidak Berharga atau Bersalah Berlebihan",
            "description": "Pengguna merasakan perasaan tidak berharga atau rasa bersalah yang berlebihan atau tidak tepat. Kalau rasa bersalah atau merasa tidak cukup muncul, biasanya dipicu oleh situasi atau pikiran seperti apa?"
        },
        {
            "name": "Gangguan Konsentrasi atau Pengambilan Keputusan",
            "description": "Pengguna mengalami kesulitan dalam konsentrasi dan fungsi eksekutif, termasuk membuat keputusan, hampir setiap hari. Jika fokus gampang buyar, apa yang biasanya mengganggu—notifikasi, kekhawatiran tertentu, atau kelelahan?"
        },
        {
            "name": "Pikiran tentang Kematian atau Bunuh Diri",
            "description": "Pengguna memiliki pikiran berulang tentang kematian, ide bunuh diri, atau percobaan bunuh diri. Jika pikiran seperti itu muncul, kapan biasanya muncul dan apa yang membuatnya terasa lebih kuat?"
        }
    ]

    # Default analysis scale (shared across all aspects)
    DEFAULT_ANALYSIS_SCALE = [
        {"value": 0, "description": "Tidak Ada Indikasi Jelas (Gejala tidak muncul dalam percakapan)"},
        {"value": 1, "description": "Indikasi Ringan (Gejala tersirat atau disebutkan secara tidak langsung)"},
        {"value": 2, "description": "Indikasi Sedang (Gejala disebutkan dengan cukup jelas, namun tidak mendominasi)"},
        {"value": 3, "description": "Indikasi Kuat (Gejala disebutkan secara eksplisit, berulang, dan menjadi keluhan utama)"}
    ]


    
    # Hard-coded System prompt - TIDAK BISA DIUBAH (Part 1)
    SYSTEM_PROMPT_FIXED = "Anda adalah Sindi, seorang mahasiswa psikologi yang supportive dan senang hati mendengarkan curhatan orang lain."
    
    # Default User Instructions - "Arahan untuk User" (what users see before starting)
    DEFAULT_USER_INSTRUCTIONS = """Anda akan memulai percakapan singkat untuk membahas aktivitas Anda akhir-akhir ini.

Di halaman selanjutnya, kami telah menyiapkan teman untuk bercerita yang akan menemani Anda menceritakan aktivitas dan apa saja yang Anda lalui dalam periode 2 minggu terakhir. Saat bercerita, cobalah untuk mengingat kembali bagaimana perasaan Anda dalam rentang waktu tersebut. Jawab pertanyaan dengan jujur dan terbuka

Tidak ada jawaban yang benar atau salah. Jawaban yang paling jujur akan memberikan hasil yang paling bermanfaat bagi anda."""

# Default LLM Instructions - Customizable (Part 2)

    DEFAULT_LLM_INSTRUCTIONS = """
Salah satu teman Anda mungkin mengalami gejala depresi, atau mungkin juga tidak. 
Tugas Anda adalah melakukan eksplorasi secara non-formal tentang aktivitas mereka selama **2 pekan terakhir**, 
dengan fokus pada aspek-aspek psikologis berikut: {aspects}
### Prinsip Percakapan
1. **Eksplorasi Aspek**
   - Gali kondisi psikologis mereka terkait setiap aspek yang disebutkan.
   - Jangan memulai topik baru yang tidak terkait; selalu kaitkan dengan apa yang sudah dibicarakan.
2. **Gaya Komunikasi**
   - Gunakan bahasa natural, non-formal, dan hangat.
   - Jika jawaban terdengar negatif, berat, atau terlalu singkat: validasi dulu secara empatik, lalu lanjutkan pelan dan jelas.
   - Gunakan emotikon bila relevan untuk terasa lebih akrab.
3. **Aturan Pertanyaan**
   - Satu pesan hanya boleh berisi **satu pertanyaan**.
   - Pertanyaan dibuat dengan panduan 2 langkah per aspek (fleksibel, tidak rigid) + 1 sampai 3 pertanyaan jika  pertanyaan belum terlalu jelas dan  membutuhkan klarifikasi lebih lanjut supaya pertanyaan nya lebih terbuka:
     - **Langkah 1:** Apakah teman menunjukkan ciri/gejala tersebut?
       - Jika tidak → jangan dilanjutkan ke langkah 2, tapi boleh diperdalam secara ringan.
     - **Langkah 2:** Jika iya, tanyakan *kenapa* dan *seberapa sering/parah* mereka mengalaminya. pastikan kenapa dan seberapa sering nya tersampaikan dengan jelas, 
     jika tidak boleh ditanya lagi atau dipancing dengan contoh-contoh general berdasarkan konteks yang diberikan pengguna contoh: homesick  -> karena jauh dari orang tua dan kangen sama orang tua 
   - Langkah bisa diperdalam lagi jika jawaban masih kurang. Gali lebih dalam bila diperlukan.
   - Jangan mengulang pertanyaan bila jawabannya sudah cukup jelas.
4. **Struktur Pertukaran**
   - Anda akan menerima indikator `turn` setiap 5 pertukaran (5, 10, 15, dst.) untuk context switching.
   - Maksimal **30 pertukaran**. Tidak harus sampai 30; hentikan bila seluruh aspek sudah dibahas.
5. **Akhir Percakapan**
   - Jika semua aspek sudah dibahas:
     - Rangkai ringkasan singkat yang positif dari apa yang mereka bagikan.
     - Tutup percakapan dengan hangat, tegaskan bahwa Anda siap mendengarkan kapanpun dibutuhkan.
     - Jika sudah selesai tanyakan apa lagi yang mau ditambahi ? 
     - jika masih belum 30 turn dan user menambahkan maka lanjutkan 
     namun tanyakn lagi kira-kira apakah sudah cukup ? dan ada yang ingin ditambahkan lagi ?
     jika sudah lebih dari 30 turn maka validasi kemudian di sudahi percakapan nya 
     - untuk mengakhiri percakapan tambahkan tag: `</end_conversation>`
"""
    INITIAL_ASSISTANT_RESPONSE = "Baik, saya akan mengeksplorasi aspek-aspek psikologis terkait gejala depresi."
    
    INTIAL_ADMIN_RESPONSE="Selanjutnya, kamu akan berhadapan dengan seseorang mahasiswa secara langsung. Silahkan memulai percakapan terlebih dahulu dengan menyapa mahasiswa tersebut."
    GREETING = "Halo aku Sindi, bagaimana kabar kamu ?"

    @staticmethod
    def get_settings() -> List[Dict[str, Any]]:
        """Get all LLM settings"""
        with get_session() as db:
            settings = db.query(LLMSettings).filter(LLMSettings.is_active == True).all()
            return [{
                'id': setting.id,
                'instructions': setting.instructions,
                'llm_instructions': setting.llm_instructions,
                'openai_api_key': setting.get_masked_api_key(),  # Return masked API key for security
                'openai_api_key_unmasked': setting.get_api_key(),  # Return unmasked API key for frontend use
                'chat_model': setting.chat_model,
                'analysis_model': setting.analysis_model,
                'depression_aspects': setting.depression_aspects.get('aspects', []) if setting.depression_aspects else [],
                'analysis_scale': setting.analysis_scale.get('scale', []) if setting.analysis_scale else [],
                'is_default': setting.is_default
            } for setting in settings]

    @staticmethod
    def create_settings(openai_api_key: Optional[str] = None, chat_model: str = "gpt-4.1-mini-2025-04-14", 
                       analysis_model: str = "gpt-4.1-mini-2025-04-14",
                       depression_aspects: Optional[List[Dict]] = None,
                       analysis_scale: Optional[List[Dict]] = None,
                       instructions: str = None,
                       llm_instructions: str = None,
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
            
            # Null handling for llm_instructions - don't save if null/empty
            final_llm_instructions = llm_instructions if llm_instructions and llm_instructions.strip() else None
            
            # Validate {aspects} placeholder exists in custom llm_instructions
            if final_llm_instructions and '{aspects}' not in final_llm_instructions:
                raise ValueError("LLM instructions must contain {aspects} placeholder")
            
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
                existing.llm_instructions = final_llm_instructions
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
                    llm_instructions=final_llm_instructions,
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
                'llm_instructions': settings.llm_instructions or '',
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
                    # Null handling for llm_instructions
                    elif key == 'llm_instructions':
                        final_value = value if value and value.strip() else None
                        # Validate {aspects} placeholder exists in custom llm_instructions
                        if final_value and '{aspects}' not in final_value:
                            raise ValueError("LLM instructions must contain {aspects} placeholder")
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
            "instructions": LLMService.DEFAULT_USER_INSTRUCTIONS.strip(),
            "llm_instructions": LLMService.DEFAULT_LLM_INSTRUCTIONS.strip(),  # Use new default instructions
            "openai_api_key": "",
            "chat_model": "gpt-4.1-mini-2025-04-14",
            "analysis_model": "gpt-4.1-mini-2025-04-14",
            "depression_aspects": LLMService.DEFAULT_ASPECTS,
            "analysis_scale": LLMService.DEFAULT_ANALYSIS_SCALE,
            "is_default": True
        }

    # DELETED: build_system_prompt() - We use ChatPromptTemplate now!
    
    @staticmethod
    def build_langchain_prompt_template(aspects: List[dict], custom_instructions: str = None):
        """Build LangChain ChatPromptTemplate with 4-part structure"""
        try:
            from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
        except ImportError:
            raise ImportError("LangChain not installed. Please install langchain-core.")
        
        # Format aspects for insertion
        aspects_text = "\n".join(f"- {aspect['name']}: {aspect['description']}" for aspect in aspects)
        
        # Use custom instructions or default
        instructions = custom_instructions if custom_instructions else LLMService.DEFAULT_LLM_INSTRUCTIONS
        
        # Validate {aspects} placeholder exists
        if '{aspects}' not in instructions:
            raise ValueError("Instructions must contain {aspects} placeholder")
        
        # Format instructions with aspects
        formatted_instructions = instructions.format(aspects=aspects_text)
        
        # Create 3-part ChatPromptTemplate + dynamic conversation
        template = ChatPromptTemplate.from_messages([
            ("system", LLMService.SYSTEM_PROMPT_FIXED),
            ("human", formatted_instructions),
            ("assistant", LLMService.INITIAL_ASSISTANT_RESPONSE),
            ("human", LLMService.INTIAL_ADMIN_RESPONSE),
            ("assistant", LLMService.GREETING),
            MessagesPlaceholder("conversation_history", optional=True),
            ("human", "{user_input}")
        ])
        return template
   
    @staticmethod
    def invoke_langchain_prompt(aspects: List[dict], 
                              custom_instructions: str = None,
                              conversation_history: List = None, 
                              user_input: str = ""):
        """Invoke the LangChain prompt template with parameters"""
        template = LLMService.build_langchain_prompt_template(aspects, custom_instructions)
        prompt_value = template.invoke({
            "conversation_history": conversation_history or [],
            "user_input": user_input
        })
        
        return prompt_value

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
        
    # Token-based auth functions for SSE

    @staticmethod
    def generate_stream_token(user_id: int, session_id: str) -> str:
        """Generate a temporary token for SSE authentication"""
        secret = "your-secret-key-here"  # TODO: Move to config
        timestamp = str(int(time.time()))
        payload = f"{user_id}:{session_id}:{timestamp}"
        signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}:{signature}"
    @staticmethod
    def validate_stream_token(token: str, max_age: int = 300) -> tuple[bool, int, str]:
        """Validate stream token, returns (valid, user_id, session_id)"""
        try:
            secret = "your-secret-key-here"  # TODO: Move to config
            parts = token.split(':')
            if len(parts) != 4:
                return False, 0, ""
            
            user_id, session_id, timestamp, signature = parts
            current_time = int(time.time())
            token_time = int(timestamp)
            
            # Check expiration
            if current_time - token_time > max_age:
                return False, 0, ""
            
            # Verify signature
            payload = f"{user_id}:{session_id}:{timestamp}"
            expected_sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
            
            if hmac.compare_digest(signature, expected_sig):
                return True, int(user_id), session_id
            
            return False, 0, ""
        except:
            return False, 0, ""


