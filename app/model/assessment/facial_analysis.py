# app/model/assessment/facial_analysis.py
from datetime import datetime
from typing import Optional, Dict, Any
import uuid
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..base import BaseModel


class SessionFacialAnalysis(BaseModel):
    """
    Stores facial expression analysis results per assessment (PHQ or LLM)

    Each assessment within a session has one analysis record that links to a JSONL file
    containing LibreFace analysis results with timing for all images in that assessment.

    The JSONL file contains one JSON object per line (one per image) with:
    - filename
    - timing (seconds_since_assessment_start, absolute_timestamp)
    - analysis (facial_expression, head_pose, action_units, key_landmarks)
    """
    __tablename__ = 'session_facial_analysis'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey('assessment_sessions.id'), nullable=False)

    # Assessment type: 'PHQ' or 'LLM'
    assessment_type: Mapped[str] = mapped_column(String(10), nullable=False)

    # Path to JSONL file containing all analysis results (relative to static/uploads/)
    # Example: "facial_analysis/session_abc123_PHQ_20250109_143022.jsonl"
    jsonl_file_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # Processing status: 'pending', 'processing', 'completed', 'failed'
    status: Mapped[str] = mapped_column(String(20), default='pending')

    # Processing metadata
    total_images_processed: Mapped[int] = mapped_column(Integer, default=0)
    images_with_faces_detected: Mapped[int] = mapped_column(Integer, default=0)
    images_failed: Mapped[int] = mapped_column(Integer, default=0)

    # Performance metrics
    processing_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_time_per_image_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Summary statistics extracted from JSONL (optional, for quick viewing)
    # Example structure:
    # {
    #   "dominant_emotion": "Happiness",
    #   "emotion_distribution": {"Neutral": 5, "Happiness": 12, "Sadness": 3},
    #   "avg_au_activations": 3.5,
    #   "most_active_aus": ["AU12", "AU6"]
    # }
    summary_stats: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Error information if processing failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationship (back_populates will be defined in AssessmentSession)
    session = relationship("AssessmentSession", back_populates="facial_analysis") 
    # To create the Migration flask cli script 1st this whole table doesnt exist at all. so remember to create this and then for the Assesment session there iss Facial analysis 
    # new relationship that looks like this 
        # from .facial_analysis import SessionFacialAnalysis
    # AssessmentSession.facial_analysis = relationship("SessionFacialAnalysis", back_populates="session", cascade="all, delete-orphan")


    def __repr__(self):
        return f'<SessionFacialAnalysis session={self.session_id} {self.assessment_type}: {self.status}, {self.total_images_processed} images>'

    @property
    def is_completed(self) -> bool:
        """Check if analysis is completed successfully"""
        return self.status == 'completed'

    @property
    def is_processing(self) -> bool:
        """Check if analysis is currently being processed"""
        return self.status == 'processing'

    @property
    def is_failed(self) -> bool:
        """Check if analysis failed"""
        return self.status == 'failed'

    @property
    def success_rate(self) -> float:
        """Calculate percentage of successfully processed images"""
        if self.total_images_processed == 0:
            return 0.0
        return (self.images_with_faces_detected / self.total_images_processed) * 100

    def get_jsonl_full_path(self, app) -> str:
        """Get absolute path to JSONL file"""
        import os
        return os.path.join(app.media_save, self.jsonl_file_path)

    def get_dominant_emotion(self) -> Optional[str]:
        """Get the most common emotion from summary stats"""
        if not self.summary_stats or 'dominant_emotion' not in self.summary_stats:
            return None
        return self.summary_stats['dominant_emotion']

    def get_emotion_distribution(self) -> Dict[str, int]:
        """Get emotion distribution from summary stats"""
        if not self.summary_stats or 'emotion_distribution' not in self.summary_stats:
            return {}
        return self.summary_stats['emotion_distribution']
