# app/schemas/export.py
"""
Pydantic schemas for export data structures.
These models define the exact shape of data exported from sessions,
making it easier for other services (like facial analysis) to consume the data.
"""
from typing import Optional
from pydantic import BaseModel


# ============================================================================
# SESSION EXPORT MODELS
# ============================================================================

class SessionExportData(BaseModel):
    """Session metadata for export"""
    session_id: str
    user_id: int
    username: str
    session_number: int
    created_at: str  # ISO format datetime string
    completed_at: Optional[str] = None  # ISO format datetime string
    status: str
    is_first: str  # 'phq' or 'llm' - which assessment comes first
    phq_completed: Optional[str] = None  # ISO format datetime string
    llm_completed: Optional[str] = None  # ISO format datetime string
    consent_completed: Optional[str] = None  # ISO format datetime string
    camera_completed: bool
    failure_reason: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "abc123",
                "user_id": 1,
                "username": "john_doe",
                "session_number": 1,
                "created_at": "2025-01-15T10:30:00",
                "completed_at": "2025-01-15T11:00:00",
                "status": "COMPLETED",
                "is_first": "phq",
                "phq_completed": "2025-01-15T10:45:00",
                "llm_completed": "2025-01-15T10:55:00",
                "consent_completed": "2025-01-15T10:31:00",
                "camera_completed": True,
                "failure_reason": None
            }
        }


# ============================================================================
# PHQ EXPORT MODELS
# ============================================================================

class PHQTimingData(BaseModel):
    """Timing data for PHQ responses (assessment-relative timing)"""
    start: Optional[int] = None  # Start time relative to assessment start (seconds)
    end: Optional[int] = None    # End time relative to assessment start (seconds)
    duration: Optional[int] = None  # Duration in seconds

    class Config:
        json_schema_extra = {
            "example": {
                "start": 0,
                "end": 0,
                "duration": 0
            }
        }


class PHQResponseItem(BaseModel):
    """Individual PHQ response item"""
    response_text: str
    response_value: int
    response_time_ms: Optional[int] = None
    timing: Optional[PHQTimingData] = None

    class Config:
        json_schema_extra = {
            "example": {
                "response_text": "Not at all",
                "response_value": 0,
                "response_time_ms": 2500,
                "timing": {
                    "assessment_start": "2025-01-15T10:35:00",
                    "assessment_end": "2025-01-15T10:35:02.5",
                    "elapsed_seconds": 2.5
                }
            }
        }


class PHQExportData(BaseModel):
    """PHQ assessment export data"""
    total_score: int
    max_possible_score: int
    responses: dict[str, dict[str, PHQResponseItem]]  # category -> question -> response

    class Config:
        json_schema_extra = {
            "example": {
                "total_score": 15,
                "max_possible_score": 27,
                "responses": {
                    "Depression": {
                        "Little interest or pleasure in doing things": {
                            "response_text": "Several days",
                            "response_value": 1,
                            "response_time_ms": 3000
                        }
                    }
                }
            }
        }


# ============================================================================
# LLM EXPORT MODELS
# ============================================================================

class LLMTimingData(BaseModel):
    """Timing data for LLM conversations (assessment-relative timing)"""
    start: Optional[int] = None  # Start time relative to assessment start (seconds)
    end: Optional[int] = None    # End time relative to assessment start (seconds)
    duration: Optional[int] = None  # Duration in seconds

    class Config:
        json_schema_extra = {
            "example": {
                "start": 2,
                "end": 3,
                "duration": 1
            }
        }


class LLMConversationTurn(BaseModel):
    """Single turn in LLM conversation"""
    turn_number: int
    created_at: str  # ISO format datetime string
    ai_message: str
    user_message: str
    user_message_length: int
    has_end_conversation: bool
    ai_model_used: Optional[str] = None
    user_timing: LLMTimingData  # Always present, may be empty dict
    ai_timing: LLMTimingData    # Always present, may be empty dict

    class Config:
        json_schema_extra = {
            "example": {
                "turn_number": 1,
                "created_at": "2025-10-11T12:19:44.099531",
                "ai_message": "Hai! Senang bisa ngobrol sama kamu.",
                "user_message": "Halo",
                "user_message_length": 4,
                "has_end_conversation": False,
                "ai_model_used": "gpt-4.1-mini-2025-04-14",
                "user_timing": {
                    "start": 2,
                    "end": 3,
                    "duration": 1
                },
                "ai_timing": {}
            }
        }


class LLMExportData(BaseModel):
    """LLM conversation export data"""
    total_conversations: int
    conversations: list[LLMConversationTurn]

    class Config:
        json_schema_extra = {
            "example": {
                "total_conversations": 5,
                "conversations": [
                    {
                        "turn_number": 1,
                        "created_at": "2025-01-15T10:50:00",
                        "ai_message": "Hello!",
                        "user_message": "Hi there",
                        "user_message_length": 8,
                        "has_end_conversation": False
                    }
                ]
            }
        }


# ============================================================================
# CAMERA CAPTURE MODELS
# ============================================================================

class CaptureTimingData(BaseModel):
    """Timing data for camera captures (assessment-relative timing)"""
    start: Optional[int] = None  # Start time relative to assessment start (seconds)
    end: Optional[int] = None    # End time relative to assessment start (seconds)
    duration: Optional[int] = None  # Duration in seconds

    class Config:
        json_schema_extra = {
            "example": {
                "start": 5,
                "end": 10,
                "duration": 5
            }
        }


class CaptureMetadata(BaseModel):
    """Metadata for individual camera capture"""
    filename: str
    timestamp: str  # ISO format datetime string
    capture_type: str  # 'PHQ' or 'LLM'
    assessment_id: str
    assessment_timing: Optional[CaptureTimingData] = None
    capture_timestamp: Optional[str] = None  # Fallback for old captures without timing

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "capture_12345.jpg",
                "timestamp": "2025-01-15T10:35:05",
                "capture_type": "PHQ",
                "assessment_id": "phq_abc123",
                "assessment_timing": {
                    "start": 5,
                    "end": 10,
                    "duration": 5
                }
            }
        }


class CaptureMetadataFull(BaseModel):
    """Extended metadata for individual camera capture (includes file paths)"""
    filename: str
    assessment_type: str  # 'PHQ' or 'LLM'
    folder_path: str
    full_path: str
    zip_path: str
    timestamp: str  # ISO format datetime string
    capture_type: str
    assessment_id: str
    assessment_timing: Optional[CaptureTimingData] = None
    capture_timestamp: Optional[str] = None  # Fallback for old captures

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "capture_12345.jpg",
                "assessment_type": "PHQ",
                "folder_path": "phq/",
                "full_path": "/path/to/media/capture_12345.jpg",
                "zip_path": "images/phq/capture_12345.jpg",
                "timestamp": "2025-01-15T10:35:05",
                "capture_type": "PHQ",
                "assessment_id": "phq_abc123",
                "assessment_timing": {
                    "start": 5,
                    "end": 10,
                    "duration": 5
                }
            }
        }


class AssessmentCaptureMetadata(BaseModel):
    """Metadata for all captures in an assessment (PHQ or LLM)"""
    assessment_type: str  # 'PHQ' or 'LLM'
    total_captures: int
    captures: list[CaptureMetadata]

    class Config:
        json_schema_extra = {
            "example": {
                "assessment_type": "PHQ",
                "total_captures": 5,
                "captures": [
                    {
                        "filename": "capture_12345.jpg",
                        "timestamp": "2025-01-15T10:35:05",
                        "capture_type": "PHQ",
                        "assessment_id": "phq_abc123"
                    }
                ]
            }
        }


class AllCapturesMetadata(BaseModel):
    """Complete metadata for all camera captures in a session"""
    total_captures: int
    phq_captures: int
    llm_captures: int
    unknown_captures_skipped: int
    captures: list[CaptureMetadataFull]

    class Config:
        json_schema_extra = {
            "example": {
                "total_captures": 10,
                "phq_captures": 5,
                "llm_captures": 5,
                "unknown_captures_skipped": 0,
                "captures": []
            }
        }
