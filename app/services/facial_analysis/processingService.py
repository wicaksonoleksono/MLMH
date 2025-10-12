"""
Facial Analysis Processing Service

This service handles the business logic for processing facial analysis:
1. Fetches session images from database
2. Calls gRPC inference service
3. Writes results to JSONL file
4. Updates database with processing status

Completely separate from gRPC service - only uses gRPC client.
"""

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from ...db import get_session
from ...model.assessment.sessions import AssessmentSession, CameraCapture, PHQResponse, LLMConversation
from ...model.assessment.facial_analysis import SessionFacialAnalysis
from ...facial_analysis.client.inference_client import FacialInferenceClient


class FacialAnalysisProcessingService:
    """Service for processing facial analysis on session images"""

    @staticmethod
    def process_session_assessment(session_id: str, assessment_type: str,
                                   media_save_path: str = None) -> Dict[str, Any]:
        """
        Process facial analysis for a specific assessment in a session

        Args:
            session_id: Assessment session ID
            assessment_type: 'PHQ' or 'LLM'
            media_save_path: Base path for media files

        Returns:
            {
                'success': bool,
                'message': str,
                'analysis_id': str,
                'jsonl_path': str,
                'stats': {...}
            }
        """
        import os

        # Get gRPC configuration from environment - NO FALLBACKS
        grpc_host = os.getenv('GRPC_FACIAL_ANALYSIS_HOST')
        grpc_port = os.getenv('GRPC_FACIAL_ANALYSIS_PORT')
        device = os.getenv('GRPC_FACIAL_ANALYSIS_DEVICE')

        if not grpc_host or not grpc_port or not device:
            raise ValueError("gRPC configuration missing in .env: GRPC_FACIAL_ANALYSIS_HOST, GRPC_FACIAL_ANALYSIS_PORT, GRPC_FACIAL_ANALYSIS_DEVICE")

        grpc_port = int(grpc_port)

        with get_session() as db:
            # Get session
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                return {'success': False, 'message': f'Session {session_id} not found'}

            # Check if already processed
            existing = db.query(SessionFacialAnalysis).filter_by(
                session_id=session_id,
                assessment_type=assessment_type
            ).first()

            if existing and existing.status == 'completed':
                return {
                    'success': False,
                    'message': f'{assessment_type} analysis already completed',
                    'analysis_id': existing.id
                }

            # Get assessment ID based on type
            assessment_id = None
            if assessment_type == 'PHQ':
                phq_response = db.query(PHQResponse).filter_by(session_id=session_id).first()
                if phq_response:
                    assessment_id = phq_response.id
                else:
                    return {'success': False, 'message': 'PHQ assessment not found'}
            elif assessment_type == 'LLM':
                llm_conversation = db.query(LLMConversation).filter_by(session_id=session_id).first()
                if llm_conversation:
                    assessment_id = llm_conversation.id
                else:
                    return {'success': False, 'message': 'LLM assessment not found'}
            else:
                return {'success': False, 'message': f'Invalid assessment_type: {assessment_type}'}

            # Get camera captures for this assessment
            captures = db.query(CameraCapture).filter_by(
                session_id=session_id,
                assessment_id=assessment_id
            ).all()

            if not captures:
                return {'success': False, 'message': f'No images found for {assessment_type} assessment'}

            # Create or update SessionFacialAnalysis record
            if existing:
                analysis_record = existing
            else:
                # Generate JSONL file path
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                jsonl_filename = f"facial_analysis/session_{session_id}_{assessment_type}_{timestamp}.jsonl"

                analysis_record = SessionFacialAnalysis(
                    session_id=session_id,
                    assessment_type=assessment_type,
                    jsonl_file_path=jsonl_filename,
                    status='pending'
                )
                db.add(analysis_record)
                db.flush()

            # Update status to processing
            analysis_record.status = 'processing'
            analysis_record.started_at = datetime.utcnow()
            db.commit()

            analysis_id = analysis_record.id

        # Process images (outside DB session to avoid long transactions)
        try:
            result = FacialAnalysisProcessingService._process_images(
                session_id=session_id,
                assessment_type=assessment_type,
                assessment_id=assessment_id,
                analysis_id=analysis_id,
                grpc_host=grpc_host,
                grpc_port=grpc_port,
                device=device,
                media_save_path=media_save_path
            )

            # Update final status
            with get_session() as db:
                analysis_record = db.query(SessionFacialAnalysis).filter_by(id=analysis_id).first()
                if result['success']:
                    analysis_record.status = 'completed'
                    analysis_record.completed_at = datetime.utcnow()
                    analysis_record.total_images_processed = result['total_processed']
                    analysis_record.images_with_faces_detected = result['faces_detected']
                    analysis_record.images_failed = result['failed']
                    analysis_record.processing_time_seconds = result['processing_time_seconds']
                    analysis_record.avg_time_per_image_ms = result['avg_time_per_image_ms']
                    analysis_record.summary_stats = result.get('summary_stats')
                else:
                    analysis_record.status = 'failed'
                    analysis_record.error_message = result['message']
                    analysis_record.completed_at = datetime.utcnow()

                db.commit()

            return result

        except Exception as e:
            # Mark as failed
            with get_session() as db:
                analysis_record = db.query(SessionFacialAnalysis).filter_by(id=analysis_id).first()
                analysis_record.status = 'failed'
                analysis_record.error_message = str(e)
                analysis_record.completed_at = datetime.utcnow()
                db.commit()

            return {'success': False, 'message': f'Processing error: {str(e)}'}

    @staticmethod
    def _process_images(session_id: str, assessment_type: str, assessment_id: str,
                       analysis_id: str, grpc_host: str, grpc_port: int,
                       device: str, media_save_path: str) -> Dict[str, Any]:
        """
        Process all images for an assessment using gRPC service

        Returns JSONL file with sorted results
        """
        start_time = datetime.now()

        with get_session() as db:
            # Get analysis record for JSONL path
            analysis = db.query(SessionFacialAnalysis).filter_by(id=analysis_id).first()
            jsonl_path = analysis.jsonl_file_path

            # Get all camera captures with timing
            captures = db.query(CameraCapture).filter_by(
                session_id=session_id,
                assessment_id=assessment_id
            ).all()

            # Extract image data with timing
            image_data = []
            for capture in captures:
                if not capture.filenames or not capture.capture_metadata:
                    continue

                capture_history = capture.capture_metadata.get('capture_history', [])

                for history_entry in capture_history:
                    filename = history_entry.get('filename')
                    timing = history_entry.get('timing', {})  # Frontend timing: {start, end, duration}
                    timestamp = history_entry.get('timestamp', '')  # ISO timestamp (absolute)

                    if filename and timing:
                        image_data.append({
                            'filename': filename,
                            'timing': timing,
                            'timestamp': timestamp
                        })

            if not image_data:
                return {'success': False, 'message': 'No valid image data found'}

            # Sort by seconds_since_assessment_start (chronological order)
            image_data.sort(key=lambda x: x['timing'].get('start', 0))

        # Connect to gRPC service
        client = FacialInferenceClient(host=grpc_host, port=grpc_port)
        if not client.connect():
            return {'success': False, 'message': 'Cannot connect to gRPC inference server'}

        # Prepare JSONL output file
        full_jsonl_path = os.path.join(media_save_path or '', jsonl_path)
        os.makedirs(os.path.dirname(full_jsonl_path), exist_ok=True)

        # Process each image
        results = []
        total_processed = 0
        faces_detected = 0
        failed = 0
        total_inference_time_ms = 0

        with open(full_jsonl_path, 'w') as jsonl_file:
            for img_data in image_data:
                filename = img_data['filename']
                timing = img_data['timing']  # {start, end, duration}
                timestamp = img_data['timestamp']  # ISO timestamp

                # Full path to image
                image_path = os.path.join(media_save_path or '', filename)

                if not os.path.exists(image_path):
                    failed += 1
                    continue

                # Call gRPC service for inference
                inference_result = client.analyze_image(image_path, device=device)

                total_processed += 1

                if inference_result['success']:
                    faces_detected += 1
                    total_inference_time_ms += inference_result.get('processing_time_ms', 0)

                    # Build JSONL entry - keep timing simple
                    # timing: {start, end, duration} where start = seconds since assessment start
                    # Images sorted by start, so line order = temporal order (1s intervals)
                    jsonl_entry = {
                        'filename': filename,
                        'assessment_type': assessment_type,
                        'timing': timing,  # Keep as-is: {start, end, duration}
                        'timestamp': timestamp,  # ISO timestamp
                        'analysis': {
                            'facial_expression': inference_result['facial_expression'],
                            'head_pose': inference_result['head_pose'],
                            'action_units': inference_result['action_units'],
                            'au_intensities': inference_result['au_intensities'],
                            'key_landmarks': inference_result['key_landmarks']
                        },
                        'inference_time_ms': inference_result['processing_time_ms']
                    }

                    results.append(jsonl_entry)

                    # Write to JSONL (one JSON object per line)
                    jsonl_file.write(json.dumps(jsonl_entry) + '\n')
                else:
                    failed += 1

        client.disconnect()

        # Calculate summary stats
        summary_stats = FacialAnalysisProcessingService._calculate_summary(results)

        # Calculate processing metrics
        end_time = datetime.now()
        processing_time_seconds = (end_time - start_time).total_seconds()
        avg_time_per_image_ms = total_inference_time_ms / faces_detected if faces_detected > 0 else 0

        return {
            'success': True,
            'message': f'Processed {total_processed} images',
            'analysis_id': analysis_id,
            'jsonl_path': jsonl_path,
            'total_processed': total_processed,
            'faces_detected': faces_detected,
            'failed': failed,
            'processing_time_seconds': processing_time_seconds,
            'avg_time_per_image_ms': avg_time_per_image_ms,
            'summary_stats': summary_stats
        }

    @staticmethod
    def _calculate_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate summary statistics from analysis results"""
        if not results:
            return {}

        # Count emotion distribution
        emotion_distribution = {}
        for result in results:
            emotion = result['analysis']['facial_expression']
            emotion_distribution[emotion] = emotion_distribution.get(emotion, 0) + 1

        # Find dominant emotion
        dominant_emotion = max(emotion_distribution.items(), key=lambda x: x[1])[0] if emotion_distribution else None

        # Calculate average AU activations
        total_au_activations = 0
        au_counts = {}

        for result in results:
            aus = result['analysis']['action_units']
            active_aus = sum(1 for v in aus.values() if v == 1)
            total_au_activations += active_aus

            for au_name, au_value in aus.items():
                if au_value == 1:
                    au_counts[au_name] = au_counts.get(au_name, 0) + 1

        avg_au_activations = total_au_activations / len(results) if results else 0

        # Find most active AUs
        most_active_aus = sorted(au_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        most_active_aus = [au[0] for au in most_active_aus]

        return {
            'dominant_emotion': dominant_emotion,
            'emotion_distribution': emotion_distribution,
            'avg_au_activations': round(avg_au_activations, 2),
            'most_active_aus': most_active_aus,
            'total_frames_analyzed': len(results)
        }

    @staticmethod
    def get_processing_status(session_id: str, assessment_type: str) -> Optional[Dict[str, Any]]:
        """Get processing status for a session assessment"""
        with get_session() as db:
            analysis = db.query(SessionFacialAnalysis).filter_by(
                session_id=session_id,
                assessment_type=assessment_type
            ).first()

            if not analysis:
                return None

            return {
                'id': analysis.id,
                'status': analysis.status,
                'total_images_processed': analysis.total_images_processed,
                'images_with_faces_detected': analysis.images_with_faces_detected,
                'images_failed': analysis.images_failed,
                'processing_time_seconds': analysis.processing_time_seconds,
                'avg_time_per_image_ms': analysis.avg_time_per_image_ms,
                'summary_stats': analysis.summary_stats,
                'error_message': analysis.error_message,
                'started_at': analysis.started_at.isoformat() if analysis.started_at else None,
                'completed_at': analysis.completed_at.isoformat() if analysis.completed_at else None
            }
