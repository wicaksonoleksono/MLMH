from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import uuid
from ..shared.database import db_session
from ...decorators import api_response
from ...model.assessment import AssessmentSession, PHQResponse
from ...model.shared.users import User

class PHQService:
    """PHQ Assessment Service for Patient Health Questionnaire processing"""
    
    PHQ_QUESTIONS = [
        "Sedikit minat atau kesenangan dalam melakukan aktivitas",
        "Merasa sedih, tertekan, atau putus asa",
        "Kesulitan tidur atau tertidur, atau terlalu banyak tidur",
        "Merasa lelah atau kurang energi",
        "Nafsu makan yang buruk atau makan berlebihan",
        "Merasa buruk tentang diri sendiri atau merasa gagal atau mengecewakan keluarga",
        "Kesulitan berkonsentrasi pada hal-hal seperti membaca koran atau menonton televisi",
        "Bergerak atau berbicara sangat lambat sehingga orang lain bisa menyadarinya, atau sebaliknya menjadi gelisah atau resah",
        "Berpikir bahwa lebih baik mati atau menyakiti diri sendiri dengan cara tertentu"
    ]
    
    RESPONSE_OPTIONS = [
        {"value": 0, "text": "Tidak pernah"},
        {"value": 1, "text": "Beberapa hari"},
        {"value": 2, "text": "Lebih dari setengah hari"},
        {"value": 3, "text": "Hampir setiap hari"}
    ]
    
    INTERPRETATION_LEVELS = {
        "minimal": {"range": [0, 4], "label": "Depresi minimal"},
        "mild": {"range": [5, 9], "label": "Depresi ringan"},
        "moderate": {"range": [10, 14], "label": "Depresi sedang"},
        "moderately_severe": {"range": [15, 19], "label": "Depresi cukup berat"},
        "severe": {"range": [20, 27], "label": "Depresi berat"}
    }
    
    @staticmethod
    @api_response
    def start_phq_session(user_id: int, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Start a new PHQ assessment session"""
        user = db_session.query(User).filter_by(id=user_id).first()
        if not user:
            raise ValueError("User not found")
        
        session_token = str(uuid.uuid4())
        
        session = AssessmentSession(
            user_id=user_id,
            assessment_type='PHQ',
            session_token=session_token,
            status='STARTED',
            session_data={
                'questions': PHQService.PHQ_QUESTIONS,
                'response_options': PHQService.RESPONSE_OPTIONS,
                'current_question': 0,
                'total_questions': len(PHQService.PHQ_QUESTIONS)
            },
            metadata=metadata or {}
        )
        
        db_session.add(session)
        db_session.commit()
        
        return {
            'session_id': session.id,
            'session_token': session_token,
            'assessment_type': 'PHQ',
            'status': 'STARTED',
            'current_question': 0,
            'total_questions': len(PHQService.PHQ_QUESTIONS),
            'question_text': PHQService.PHQ_QUESTIONS[0],
            'response_options': PHQService.RESPONSE_OPTIONS
        }
    
    @staticmethod
    @api_response
    def submit_phq_response(session_token: str, question_number: int, response_value: int, 
                           response_time_ms: Optional[int] = None) -> Dict[str, Any]:
        """Submit PHQ response for a specific question"""
        session = db_session.query(AssessmentSession).filter_by(
            session_token=session_token,
            assessment_type='PHQ'
        ).first()
        
        if not session:
            raise ValueError("PHQ session not found")
        
        if session.is_completed:
            raise ValueError("Session already completed")
        
        if question_number < 0 or question_number >= len(PHQService.PHQ_QUESTIONS):
            raise ValueError("Invalid question number")
        
        if response_value not in [0, 1, 2, 3]:
            raise ValueError("Invalid response value")
        
        # Check if response already exists
        existing = db_session.query(PHQResponse).filter_by(
            session_id=session.id,
            question_number=question_number
        ).first()
        
        if existing:
            existing.response_value = response_value
            existing.response_text = next(opt['text'] for opt in PHQService.RESPONSE_OPTIONS if opt['value'] == response_value)
            existing.response_time_ms = response_time_ms
            response = existing
        else:
            response = PHQResponse(
                session_id=session.id,
                question_number=question_number,
                question_text=PHQService.PHQ_QUESTIONS[question_number],
                response_value=response_value,
                response_text=next(opt['text'] for opt in PHQService.RESPONSE_OPTIONS if opt['value'] == response_value),
                response_time_ms=response_time_ms
            )
            db_session.add(response)
        
        # Update session data
        session.session_data['current_question'] = question_number + 1
        session.updated_at = datetime.utcnow()
        
        db_session.commit()
        
        # Check if all questions answered
        total_responses = db_session.query(PHQResponse).filter_by(session_id=session.id).count()
        
        if total_responses >= len(PHQService.PHQ_QUESTIONS):
            return PHQService._complete_phq_session(session)
        
        # Return next question
        next_question = question_number + 1
        return {
            'session_id': session.id,
            'current_question': next_question,
            'total_questions': len(PHQService.PHQ_QUESTIONS),
            'question_text': PHQService.PHQ_QUESTIONS[next_question] if next_question < len(PHQService.PHQ_QUESTIONS) else None,
            'response_options': PHQService.RESPONSE_OPTIONS,
            'progress_percentage': round((total_responses / len(PHQService.PHQ_QUESTIONS)) * 100, 2)
        }
    
    @staticmethod
    def _complete_phq_session(session: AssessmentSession) -> Dict[str, Any]:
        """Complete PHQ session and calculate results"""
        responses = db_session.query(PHQResponse).filter_by(session_id=session.id).all()
        
        if len(responses) != len(PHQService.PHQ_QUESTIONS):
            raise ValueError("Incomplete PHQ responses")
        
        # Calculate total score
        total_score = sum(response.response_value for response in responses)
        
        # Determine severity level
        severity_level = PHQService._get_severity_level(total_score)
        
        # Calculate response statistics
        response_times = [r.response_time_ms for r in responses if r.response_time_ms]
        avg_response_time = sum(response_times) / len(response_times) if response_times else None
        
        results = {
            'total_score': total_score,
            'severity_level': severity_level['level'],
            'severity_label': severity_level['label'],
            'interpretation': severity_level['interpretation'],
            'response_breakdown': {
                str(i): count for i, count in enumerate([
                    sum(1 for r in responses if r.response_value == i) for i in range(4)
                ])
            },
            'average_response_time_ms': avg_response_time,
            'completion_time': datetime.utcnow().isoformat()
        }
        
        session.complete_session(results)
        db_session.commit()
        
        return {
            'session_id': session.id,
            'status': 'COMPLETED',
            'results': results,
            'completion_message': f"PHQ-9 selesai dengan skor {total_score} ({severity_level['label']})"
        }
    
    @staticmethod
    def _get_severity_level(score: int) -> Dict[str, Any]:
        """Determine PHQ severity level from total score"""
        for level, data in PHQService.INTERPRETATION_LEVELS.items():
            if data['range'][0] <= score <= data['range'][1]:
                return {
                    'level': level,
                    'label': data['label'],
                    'interpretation': PHQService._get_interpretation_text(level, score)
                }
        
        return {
            'level': 'severe',
            'label': 'Depresi berat',
            'interpretation': 'Skor menunjukkan tingkat depresi yang sangat tinggi'
        }
    
    @staticmethod
    def _get_interpretation_text(level: str, score: int) -> str:
        """Get detailed interpretation text for severity level"""
        interpretations = {
            'minimal': f'Skor {score} menunjukkan tingkat depresi minimal. Gejala depresi sangat ringan atau tidak ada.',
            'mild': f'Skor {score} menunjukkan tingkat depresi ringan. Beberapa gejala depresi hadir namun masih dapat dikelola.',
            'moderate': f'Skor {score} menunjukkan tingkat depresi sedang. Gejala depresi cukup mengganggu aktivitas sehari-hari.',
            'moderately_severe': f'Skor {score} menunjukkan tingkat depresi cukup berat. Gejala depresi signifikan dan memerlukan perhatian.',
            'severe': f'Skor {score} menunjukkan tingkat depresi berat. Gejala depresi sangat mengganggu dan memerlukan bantuan profesional.'
        }
        return interpretations.get(level, f'Skor {score} memerlukan evaluasi lebih lanjut.')
    
    @staticmethod
    @api_response
    def get_phq_session(session_token: str) -> Dict[str, Any]:
        """Get PHQ session details"""
        session = db_session.query(AssessmentSession).filter_by(
            session_token=session_token,
            assessment_type='PHQ'
        ).first()
        
        if not session:
            raise ValueError("PHQ session not found")
        
        responses = db_session.query(PHQResponse).filter_by(session_id=session.id).all()
        
        return {
            'session_id': session.id,
            'status': session.status,
            'created_at': session.created_at.isoformat(),
            'is_completed': session.is_completed,
            'current_question': session.session_data.get('current_question', 0),
            'total_questions': len(PHQService.PHQ_QUESTIONS),
            'responses_count': len(responses),
            'results': session.results if session.is_completed else None,
            'responses': [
                {
                    'question_number': r.question_number,
                    'question_text': r.question_text,
                    'response_value': r.response_value,
                    'response_text': r.response_text,
                    'response_time_ms': r.response_time_ms
                } for r in responses
            ]
        }
    
    @staticmethod
    @api_response
    def get_user_phq_history(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get PHQ assessment history for user"""
        sessions = db_session.query(AssessmentSession).filter_by(
            user_id=user_id,
            assessment_type='PHQ'
        ).order_by(AssessmentSession.created_at.desc()).limit(limit).all()
        
        return [
            {
                'session_id': session.id,
                'session_token': session.session_token,
                'status': session.status,
                'created_at': session.created_at.isoformat(),
                'completed_at': session.end_time.isoformat() if session.end_time else None,
                'duration_seconds': session.duration_seconds,
                'total_score': session.results.get('total_score') if session.results else None,
                'severity_level': session.results.get('severity_level') if session.results else None,
                'severity_label': session.results.get('severity_label') if session.results else None
            } for session in sessions
        ]