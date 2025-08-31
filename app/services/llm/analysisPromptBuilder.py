# app/services/llm/analysisPromptBuilder.py
from typing import List, Dict, Any, Optional
import json

class LLMAnalysisPromptBuilder:
    """
    Builds analysis prompts for LLM conversation analysis.
    Separates prompt construction logic from analysis execution.
    """
    
    PSYCHOLOGIST_INTRO = """Anda adalah seorang psikolog. Kemudian terdapat 2 orang yang sedang melakukan percakapan, yaitu Anisa seorang mahasiswa psikologi yang supportive dan senang hati mendengarkan curhatan orang lain, dan temannya, dimana Anisa bertindak sebagai orang yang sedang mendengarkan curhat temannya yang kemungkinan mengalami gejala depresi, atau bisa jadi tidak. 

Berikut adalah hasil percakapan untuk mengeksplorasi bagaimana kondisi psikologis mereka terutama yang berkaitan dengan gejala depresi:"""

    @staticmethod
    def format_chat_history(conversation_messages: List[Dict[str, str]]) -> str:
        """
        Format conversation messages into simple Anisa/Teman format.
        
        Args:
            conversation_messages: List of {"role": "assistant|user", "message": "content"}
            
        Returns:
            Formatted chat history string: "Anisa: {ai_message}\nTeman: {human_message}\n"
        """
        formatted_lines = []
        
        for msg in conversation_messages:
            role = msg.get('role', 'user')
            content = msg.get('message', '').strip()
            
            if not content:
                continue
                
            # Map roles to conversation participants
            speaker = "Anisa" if role == "assistant" else "Teman"
            formatted_lines.append(f"{speaker}: {content}")
        
        return "\n".join(formatted_lines)

    @staticmethod
    def build_aspects_section(depression_aspects: List[Dict[str, Any]]) -> str:
        """
        Build the aspects description section.
        
        Args:
            depression_aspects: List of aspect dictionaries with name/description
            
        Returns:
            Formatted aspects string: "- Anhedonia: kehilangan minat/kenikmatan\n- ..."
        """
        aspects_lines = []
        
        for aspect in depression_aspects:
            name = aspect.get('name', 'Unknown')
            description = aspect.get('description', 'No description')
            aspects_lines.append(f"- {name}: {description}")
        
        return "\n".join(aspects_lines)

    @staticmethod
    def build_scoring_section(depression_aspects: List[Dict[str, Any]], analysis_scale: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        Build the scoring scale descriptions section.
        
        Args:
            depression_aspects: List of depression aspects
            analysis_scale: Shared analysis scale configuration (if available)
            
        Returns:
            Formatted scoring descriptions
        """
        # Get default scale descriptions (will be same for all aspects initially)
        default_scales = {
            "0": "Tidak Ada Indikasi Jelas (Gejala tidak muncul dalam percakapan)",
            "1": "Indikasi Ringan (Gejala tersirat atau disebutkan secara tidak langsung)",
            "2": "Indikasi Sedang (Gejala disebutkan dengan cukup jelas, namun tidak mendominasi)",
            "3": "Indikasi Kuat (Gejala disebutkan secara eksplisit, berulang, dan menjadi keluhan utama)"
        }
        
        # Use custom analysis_scale if provided, otherwise check old format or use defaults
        scale_descriptions = default_scales
        if analysis_scale and len(analysis_scale) > 0:
            # Use the new shared analysis_scale format
            scale_dict = {}
            for scale_item in analysis_scale:
                if 'value' in scale_item and 'description' in scale_item:
                    scale_dict[str(scale_item['value'])] = scale_item['description']
            if scale_dict:
                scale_descriptions = scale_dict
        elif depression_aspects and len(depression_aspects) > 0:
            # Fallback to old format for backward compatibility
            first_aspect = depression_aspects[0]
            if 'analysis_config' in first_aspect and 'scale_descriptions' in first_aspect['analysis_config']:
                scale_descriptions = first_aspect['analysis_config']['scale_descriptions']
        
        scale_lines = []
        for scale_value in ["0", "1", "2", "3"]:
            description = scale_descriptions.get(scale_value, f"Scale {scale_value}: No description")
            scale_lines.append(f"{scale_value}: {description}")
        
        return "\n".join(scale_lines)

    @staticmethod
    def build_json_format_example(depression_aspects: List[Dict[str, Any]]) -> str:
        """
        Build the expected JSON output format example.
        
        Args:
            depression_aspects: List of aspects to create format for
            
        Returns:
            JSON format example string
        """
        json_structure = {}
        
        for i, aspect in enumerate(depression_aspects, 1):
            # Convert aspect name to valid JSON key format
            aspect_name = aspect.get('name', f'indicator_{i}').lower().replace(' ', '_')
            json_structure[aspect_name] = {
                "penjelasan": f"penjelasan {i}",
                "skor": f"ESTIMATED_SCORE_{i}"
            }
        
        return json.dumps(json_structure, indent=2, ensure_ascii=False)

    @classmethod
    def build_full_analysis_prompt(
        cls, 
        conversation_messages: List[Dict[str, str]], 
        depression_aspects: List[Dict[str, Any]],
        analysis_scale: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Build the complete analysis prompt.
        
        Args:
            conversation_messages: Chat history messages
            depression_aspects: Depression aspects configuration
            analysis_scale: Shared analysis scale configuration (optional)
            
        Returns:
            Complete analysis prompt string
        """
        chat_history = cls.format_chat_history(conversation_messages)
        aspects_section = cls.build_aspects_section(depression_aspects)
        scoring_section = cls.build_scoring_section(depression_aspects, analysis_scale)
        json_format = cls.build_json_format_example(depression_aspects)
        
        prompt = f"""{cls.PSYCHOLOGIST_INTRO}

{chat_history}

Berdasarkan indikator-indikator dari gejala depresi berikut:
{aspects_section}

Buatlah analisa jawaban "Teman" diatas untuk setiap indikator tersebut beserta penilaian skala angka (0-3):
{scoring_section}

Gunakan format JSON berikut, mohon jangan menulis yang tidak diminta, penjelasan maksimal 2 kalimat:
{json_format}"""

        return prompt