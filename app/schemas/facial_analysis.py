# app/schemas/facial_analysis.py
"""
Pydantic schemas for facial analysis data structures.
These models define the exact shape of facial analysis results,
ensuring consistency with export schemas and type safety.
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from .export import CaptureTimingData


# ============================================================================
# FACIAL ANALYSIS COMPONENT MODELS
# ============================================================================

class HeadPoseData(BaseModel):
    """Head pose estimation (yaw, pitch, roll in degrees)"""
    yaw: float
    pitch: float
    roll: float

    class Config:
        json_schema_extra = {
            "example": {
                "yaw": 0.5,
                "pitch": 0.2,
                "roll": 0.1
            }
        }


class FacialAnalysisData(BaseModel):
    """Complete facial analysis for one image from LibreFace gRPC"""
    facial_expression: str  # e.g., "neutral", "happy", "sad"
    head_pose: HeadPoseData
    action_units: Dict[str, int]  # e.g., {"au_1": 1, "au_2": 0, "au_4": 1} from gRPC
    au_intensities: Dict[str, float]  # e.g., {"au_1": 2.5, "au_2": 0.0} from gRPC
    key_landmarks: List[Dict[str, Any]]  # List of {index: int, x: float, y: float, z: float}

    class Config:
        json_schema_extra = {
            "example": {
                "facial_expression": "neutral",
                "head_pose": {
                    "yaw": 0.5,
                    "pitch": 0.2,
                    "roll": 0.1
                },
                "action_units": {
                    "au_1": 1,
                    "au_2": 0,
                    "au_4": 1
                },
                "au_intensities": {
                    "au_1": 2.5,
                    "au_2": 0.0,
                    "au_4": 1.8
                },
                "key_landmarks": [
                    {"index": 0, "x": 120.5, "y": 150.3, "z": 0.0},
                    {"index": 1, "x": 125.2, "y": 148.7, "z": 0.0}
                ]
            }
        }


# ============================================================================
# INDIVIDUAL IMAGE RESULT MODEL
# ============================================================================

class FacialAnalysisImageResult(BaseModel):
    """Facial analysis result for a single image"""
    filename: str
    assessment_type: str  # 'PHQ' or 'LLM'
    timing: CaptureTimingData  # Reuse from export schemas for consistency
    timestamp: str  # ISO format datetime string
    analysis: FacialAnalysisData  # Structured facial analysis data
    inference_time_ms: int

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "capture_12345.jpg",
                "assessment_type": "PHQ",
                "timing": {
                    "start": 5,
                    "end": 6,
                    "duration": 1
                },
                "timestamp": "2025-10-15T14:30:05",
                "analysis": {
                    "facial_expression": "neutral",
                    "head_pose": {
                        "yaw": 0.5,
                        "pitch": 0.2,
                        "roll": 0.1
                    },
                    "action_units": {"au_1": 1, "au_2": 0},
                    "au_intensities": {"au_1": 2.5},
                    "key_landmarks": [{"index": 0, "x": 120.5, "y": 150.3, "z": 0.0}]
                },
                "inference_time_ms": 45
            }
        }


# ============================================================================
# SUMMARY STATISTICS MODEL
# ============================================================================

class FacialAnalysisSummaryStats(BaseModel):
    """Summary statistics for all images in an assessment"""
    dominant_emotion: Optional[str] = None
    emotion_distribution: Dict[str, int]  # e.g., {"neutral": 10, "happy": 5}
    avg_au_activations: float  # Average number of active AUs per image
    most_active_aus: List[str]  # Top 5 most frequently activated AUs
    total_frames_analyzed: int

    class Config:
        json_schema_extra = {
            "example": {
                "dominant_emotion": "neutral",
                "emotion_distribution": {
                    "neutral": 10,
                    "happy": 3,
                    "sad": 2
                },
                "avg_au_activations": 3.5,
                "most_active_aus": ["au_1", "au_4", "au_6", "au_12", "au_15"],
                "total_frames_analyzed": 15
            }
        }


# ============================================================================
# PROCESSING MODELS (Internal use for service logic)
# ============================================================================

class ImageDataForProcessing(BaseModel):
    """Image data prepared for gRPC processing (internal service use)"""
    filename: str
    timing: CaptureTimingData
    timestamp: str  # ISO format

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "capture_12345.jpg",
                "timing": {"start": 5, "end": 6, "duration": 1},
                "timestamp": "2025-10-15T14:30:05"
            }
        }


class ProcessingResult(BaseModel):
    """Result returned from processing a session assessment"""
    success: bool
    message: str
    analysis_id: Optional[str] = None
    results_path: Optional[str] = None
    total_processed: int = 0
    faces_detected: int = 0
    failed: int = 0
    processing_time_seconds: float = 0.0
    avg_time_per_image_ms: float = 0.0
    summary_stats: Optional[Dict[str, Any]] = None
    errors: Optional[List[Dict[str, Any]]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Processed 15 images",
                "analysis_id": "analysis_abc123",
                "results_path": "facial_analysis/session_xyz_PHQ_20251015.jsonl",
                "total_processed": 15,
                "faces_detected": 15,
                "failed": 0,
                "processing_time_seconds": 5.2,
                "avg_time_per_image_ms": 45.3,
                "summary_stats": {"dominant_emotion": "neutral"}
            }
        }


class ProcessingStatus(BaseModel):
    """Status of facial analysis processing for an assessment"""
    id: str
    status: str  # 'pending', 'processing', 'completed', 'failed'
    total_images_processed: Optional[int] = None
    images_with_faces_detected: Optional[int] = None
    images_failed: Optional[int] = None
    processing_time_seconds: Optional[float] = None
    avg_time_per_image_ms: Optional[float] = None
    summary_stats: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[str] = None  # ISO format
    completed_at: Optional[str] = None  # ISO format

    class Config:
        json_schema_extra = {
            "example": {
                "id": "analysis_abc123",
                "status": "completed",
                "total_images_processed": 15,
                "images_with_faces_detected": 15,
                "images_failed": 0,
                "processing_time_seconds": 5.2,
                "avg_time_per_image_ms": 45.3,
                "summary_stats": {"dominant_emotion": "neutral"},
                "error_message": None,
                "started_at": "2025-10-15T14:30:00",
                "completed_at": "2025-10-15T14:35:12"
            }
        }


# ============================================================================
# WRAPPER MODEL FOR COMPLETE ASSESSMENT RESULTS
# ============================================================================

class AssessmentFacialAnalysis(BaseModel):
    """
    Complete facial analysis results for one assessment (PHQ or LLM).
    This is the wrapper model that contains all results + metadata.
    Saved as one JSON file per assessment.
    """
    session_id: str
    assessment_id: str
    assessment_type: str  # 'PHQ' or 'LLM'
    total_images: int
    results: List[FacialAnalysisImageResult]
    summary_stats: Optional[FacialAnalysisSummaryStats] = None
    processing_metadata: Optional[Dict[str, Any]] = None  # e.g., processing_time, avg_inference_time

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_abc123",
                "assessment_id": "phq_xyz789",
                "assessment_type": "PHQ",
                "total_images": 15,
                "results": [
                    {
                        "filename": "capture_12345.jpg",
                        "assessment_type": "PHQ",
                        "timing": {"start": 5, "end": 6, "duration": 1},
                        "timestamp": "2025-10-15T14:30:05",
                        "analysis": {
                            "facial_expression": "neutral",
                            "head_pose": {"yaw": 0.5, "pitch": 0.2, "roll": 0.1},
                            "action_units": {"au_1": 1},
                            "au_intensities": {"au_1": 2.5},
                            "key_landmarks": []
                        },
                        "inference_time_ms": 45
                    }
                ],
                "summary_stats": {
                    "dominant_emotion": "neutral",
                    "emotion_distribution": {"neutral": 10, "happy": 5},
                    "avg_au_activations": 3.5,
                    "most_active_aus": ["au_1", "au_4", "au_6"],
                    "total_frames_analyzed": 15
                },
                "processing_metadata": {
                    "processing_time_seconds": 5.2,
                    "avg_time_per_image_ms": 45.3,
                    "faces_detected": 15,
                    "failed": 0
                }
            }
        }
