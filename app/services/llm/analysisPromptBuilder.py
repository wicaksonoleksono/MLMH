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
    def build_scoring_section(depression_aspects: List[Dict[str, Any]], analysis_scale: List[Dict[str, Any]]) -> str:
        """
        Build the scoring scale descriptions section using shared analysis scale.
        
        Args:
            depression_aspects: List of depression aspects
            analysis_scale: Shared analysis scale configuration (REQUIRED)
            
        Returns:
            Formatted scoring descriptions
        """
        if not analysis_scale or len(analysis_scale) == 0:
            raise ValueError("analysis_scale is required and cannot be empty")
        
        # Convert analysis_scale to descriptions
        scale_descriptions = {}
        for scale_item in analysis_scale:
            if 'value' in scale_item and 'description' in scale_item:
                scale_descriptions[str(scale_item['value'])] = scale_item['description']
        
        if not scale_descriptions:
            raise ValueError("Invalid analysis_scale format - no valid value/description pairs found")
        
        # Build scale lines in order
        scale_lines = []
        for value in sorted(scale_descriptions.keys(), key=int):
            description = scale_descriptions[value]
            scale_lines.append(f"{value}: {description}")
        
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
        analysis_scale: List[Dict[str, Any]]
    ) -> str:
        """
        Build the complete analysis prompt.
        
        Args:
            conversation_messages: Chat history messages
            depression_aspects: Depression aspects configuration
            analysis_scale: Shared analysis scale configuration (REQUIRED)
            
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