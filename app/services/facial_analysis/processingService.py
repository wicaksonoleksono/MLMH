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
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import asyncio

from ...db import get_session
from .asyncBatchProcessor import BatchedAsyncProcessor
from ...model.assessment.sessions import AssessmentSession, CameraCapture, PHQResponse, LLMConversation
from ...model.assessment.facial_analysis import SessionFacialAnalysis
from ...facial_analysis.client.inference_client import FacialInferenceClient
from ...schemas.export import CaptureTimingData
from ...schemas.facial_analysis import (
    HeadPoseData,
    FacialAnalysisData,
    FacialAnalysisImageResult,
    ImageDataForProcessing,
    ProcessingResult,
    ProcessingStatus
)


class FacialAnalysisProcessingService:
    """Service for processing facial analysis on session images"""

    @staticmethod
    def process_session_assessment(session_id: str, assessment_type: str,
                                   media_save_path: Optional[str] = None) -> ProcessingResult:
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
                return ProcessingResult(success=False, message=f'Session {session_id} not found')

            # Check if already processed
            existing = db.query(SessionFacialAnalysis).filter_by(
                session_id=session_id,
                assessment_type=assessment_type
            ).first()

            if existing and existing.status == 'completed':
                return ProcessingResult(
                    success=False,
                    message=f'{assessment_type} analysis already completed',
                    analysis_id=existing.id
                )

            # Get assessment ID based on type
            assessment_id = None
            if assessment_type == 'PHQ':
                phq_response = db.query(PHQResponse).filter_by(session_id=session_id).first()
                if phq_response:
                    assessment_id = phq_response.id
                else:
                    return ProcessingResult(success=False, message='PHQ assessment not found')
            elif assessment_type == 'LLM':
                llm_conversation = db.query(LLMConversation).filter_by(session_id=session_id).first()
                if llm_conversation:
                    assessment_id = llm_conversation.id
                else:
                    return ProcessingResult(success=False, message='LLM assessment not found')
            else:
                return ProcessingResult(success=False, message=f'Invalid assessment_type: {assessment_type}')

            # Get camera captures for this assessment
            captures = db.query(CameraCapture).filter_by(
                session_id=session_id,
                assessment_id=assessment_id
            ).all()

            if not captures:
                return ProcessingResult(success=False, message=f'No images found for {assessment_type} assessment')

            # Create or update SessionFacialAnalysis record
            if existing:
                analysis_record = existing
            else:
                # Generate JSONL file path for streaming results with wrapper
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                results_filename = f"facial_analysis/session_{session_id}_{assessment_type}_{timestamp}.jsonl"

                analysis_record = SessionFacialAnalysis(
                    session_id=session_id,
                    assessment_type=assessment_type,
                    jsonl_file_path=results_filename,
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
                if not analysis_record:
                    # Record was deleted or lost - log and continue
                    return result

                if result.success:
                    analysis_record.status = 'completed'
                    analysis_record.completed_at = datetime.utcnow()
                    analysis_record.total_images_processed = result.total_processed
                    analysis_record.images_with_faces_detected = result.faces_detected
                    analysis_record.images_failed = result.failed
                    analysis_record.processing_time_seconds = result.processing_time_seconds
                    analysis_record.avg_time_per_image_ms = result.avg_time_per_image_ms
                    analysis_record.summary_stats = result.summary_stats
                else:
                    analysis_record.status = 'failed'
                    analysis_record.error_message = result.message
                    analysis_record.completed_at = datetime.utcnow()

                db.commit()

            return result

        except Exception as e:
            # Mark as failed
            with get_session() as db:
                analysis_record = db.query(SessionFacialAnalysis).filter_by(id=analysis_id).first()
                if not analysis_record:
                    # Record was deleted or lost - log and return error
                    return ProcessingResult(success=False, message=f'Processing error: {str(e)}')

                analysis_record.status = 'failed'
                analysis_record.error_message = str(e)
                analysis_record.completed_at = datetime.utcnow()
                db.commit()

            return ProcessingResult(success=False, message=f'Processing error: {str(e)}')

    @staticmethod
    def _process_images(session_id: str, assessment_type: str, assessment_id: str,
                       analysis_id: str, grpc_host: str, grpc_port: int,
                       device: str, media_save_path: Optional[str]) -> ProcessingResult:
        """
        Process all images for an assessment using gRPC service

        Writes JSONL file with streaming:
        - Line 1: Metadata wrapper
        - Lines 2-N: Individual image results (streamed as processed)
        - Last line: Summary stats
        """
        start_time = datetime.now()

        with get_session() as db:
            # Get analysis record for results file path
            analysis = db.query(SessionFacialAnalysis).filter_by(id=analysis_id).first()
            results_path = analysis.jsonl_file_path  # DB field stores .jsonl file path

            # Get all camera captures with timing
            captures = db.query(CameraCapture).filter_by(
                session_id=session_id,
                assessment_id=assessment_id
            ).all()

            # Extract image data with timing - MATCH EXPORT SERVICE METHOD
            image_data: List[ImageDataForProcessing] = []

            for capture in captures:
                # Skip if no filenames (match export service logic)
                if not capture.filenames:
                    continue


                # Iterate through filenames array (match export service)
                for filename in capture.filenames:
                    # Extract timing data if available
                    timing_dict = None
                    timestamp = None

                    if capture.capture_metadata and 'capture_history' in capture.capture_metadata:
                        capture_history = capture.capture_metadata['capture_history']
                        # Find the entry for this filename
                        for entry in capture_history:
                            if entry.get('filename') == filename:
                                timing_dict = entry.get('timing', {})
                                timestamp = entry.get('timestamp', '')
                                break

                    # For old captures without timing, use the capture timestamp
                    if not timing_dict:
                        timestamp = capture.created_at.isoformat()
                        timing_dict = {}

                    # Create Pydantic model for timing (consistent with export schemas)
                    timing_model = CaptureTimingData(**timing_dict) if timing_dict else CaptureTimingData()

                    # Create structured image data model
                    img_data = ImageDataForProcessing(
                        filename=filename,
                        timing=timing_model,
                        timestamp=timestamp or capture.created_at.isoformat()
                    )
                    image_data.append(img_data)


            if not image_data:
                return ProcessingResult(success=False, message='No valid image data found')

            # Sort by seconds_since_assessment_start (chronological order)
            image_data.sort(key=lambda x: x.timing.start if x.timing.start else 0)

        # Connect to gRPC service
        client = FacialInferenceClient(host=grpc_host, port=grpc_port)
        if not client.connect():
            return ProcessingResult(success=False, message='Cannot connect to gRPC inference server')

        # Prepare output file path
        full_results_path = os.path.join(media_save_path or '', results_path)
        os.makedirs(os.path.dirname(full_results_path), exist_ok=True)

        # PHASE 1: Memoize input metadata in memory (sequential mapping)
        # NOTE: Only caching FILENAMES & PATHS, NOT image data (images stay on disk)
        # This allows processing 1000s of images without RAM issues (e.g., 40GB+ image sets)
        image_cache = {}  # Map index → filename/path/timing metadata (lightweight)

        # Get storage path from camera settings (same as where images are saved)
        from ...services.camera.cameraStorageService import CameraStorageService
        storage_path = CameraStorageService.get_storage_path_for_session(session_id)
        if not storage_path:
            storage_path = media_save_path or ''

        for idx, img_data in enumerate(image_data):
            # Build full image path (same way it was saved)
            # Images are saved to storage_path (absolute path from camera settings)
            image_path = os.path.join(storage_path, img_data.filename)

            # Ensure path is absolute - if relative, prepend media_save_path
            if not os.path.isabs(image_path) and media_save_path:
                image_path = os.path.join(media_save_path, image_path)

            image_cache[idx] = {
                'index': idx,
                'filename': img_data.filename,
                'timing': img_data.timing,
                'timestamp': img_data.timestamp,
                'image_path': image_path
            }

        # Open JSONL file for streaming writes
        results_for_summary: List[FacialAnalysisImageResult] = []
        total_processed = 0
        faces_detected = 0
        failed = 0
        total_inference_time_ms = 0
        failure_details: List[Dict[str, Any]] = []

        # Thread-safe locks for shared state
        stats_lock = threading.Lock()

        with open(full_results_path, 'w') as jsonl_file:
            # Line 1: Write metadata wrapper (minimal, no worker info)
            metadata = {
                'type': 'metadata',
                'session_id': session_id,
                'assessment_id': assessment_id,
                'assessment_type': assessment_type,
                'total_images': len(image_data),
                'started_at': start_time.isoformat()
            }
            jsonl_file.write(json.dumps(metadata) + '\n')

            # Process images in parallel using ThreadPoolExecutor
            # 4 workers match the gRPC server workers

            def process_single_image(idx):
                """Process a single image using cached metadata"""
                # Retrieve from memory cache (already has all metadata sequentially mapped)
                cached = image_cache[idx]
                filename = cached['filename']
                timing = cached['timing']
                timestamp = cached['timestamp']
                image_path = cached['image_path']

                result_entry = {
                    'index': idx,
                    'filename': filename,
                    'timing': timing,
                    'timestamp': timestamp,
                    'inference_result': None,
                    'success': False,
                    'error': None
                }

                # Check if image exists
                if not os.path.exists(image_path):
                    result_entry['error'] = f'Image not found: {image_path}'
                    return result_entry

                # Call gRPC service for inference (parallel!)
                try:
                    inference_result = client.analyze_image(image_path, device=device)
                    result_entry['inference_result'] = inference_result
                    result_entry['success'] = inference_result.get('success', False)

                    if not result_entry['success']:
                        result_entry['error'] = inference_result.get('error_message', 'Unknown error')

                    return result_entry
                except Exception as e:
                    result_entry['error'] = str(e)
                    return result_entry

            # PHASE 2: Process images in parallel using cached metadata
            # Submit all images to thread pool for parallel processing
            results_by_index = {}  # Store results keyed by original image index
            import time
            phase2_start = time.time()

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(process_single_image, idx): idx
                    for idx in range(len(image_cache))
                }

                # Collect all results (can complete in any order from threads)
                completed_count = 0
                for future in as_completed(futures):
                    try:
                        result_entry = future.result()
                        idx = result_entry['index']
                        results_by_index[idx] = result_entry
                        completed_count += 1
                    except Exception as e:
                        # Continue processing even if one thread fails
                        continue

                phase2_time = time.time() - phase2_start
                missing_indices = [i for i in range(len(image_cache)) if i not in results_by_index]

            # PHASE 3: Write results to JSONL in SEQUENTIAL order (reorder by original mapping)
            missing_indices = []
            for idx in range(len(image_data)):
                if idx not in results_by_index:
                    missing_indices.append(idx)
                    continue

                result_entry = results_by_index[idx]
                filename = result_entry['filename']
                timing = result_entry['timing']
                timestamp = result_entry['timestamp']
                inference_result = result_entry['inference_result']

                with stats_lock:
                    total_processed += 1

                if result_entry['error']:
                    with stats_lock:
                        failed += 1

                    error_message = result_entry['error']

                    failure_detail = {
                        'filename': filename,
                        'assessment_type': assessment_type,
                        'timestamp': timestamp,
                        'error_message': error_message
                    }
                    failure_details.append(failure_detail)

                    error_entry = {
                        'type': 'error',
                        'filename': filename,
                        'assessment_type': assessment_type,
                        'timestamp': timestamp,
                        'message': error_message
                    }
                    timing_dict = timing.model_dump(exclude_none=True)
                    if timing_dict:
                        error_entry['timing'] = timing_dict

                    jsonl_file.write(json.dumps(error_entry) + '\n')
                    continue

                if inference_result and inference_result['success']:
                    with stats_lock:
                        faces_detected += 1
                        total_inference_time_ms += inference_result.get('processing_time_ms', 0)

                    # Build structured Pydantic models for analysis data
                    head_pose = HeadPoseData(**inference_result['head_pose'])

                    facial_analysis = FacialAnalysisData(
                        facial_expression=inference_result['facial_expression'],
                        head_pose=head_pose,
                        action_units=inference_result['action_units'],
                        au_intensities=inference_result['au_intensities'],
                        key_landmarks=inference_result['key_landmarks']
                    )

                    # Create complete image result using Pydantic model
                    image_result = FacialAnalysisImageResult(
                        filename=filename,
                        assessment_type=assessment_type,
                        timing=timing,
                        timestamp=timestamp,
                        analysis=facial_analysis,
                        inference_time_ms=inference_result['processing_time_ms']
                    )

                    # Keep for summary calculation
                    results_for_summary.append(image_result)

                    # Write to JSONL in sequential order
                    result_dict = image_result.model_dump()
                    result_dict['type'] = 'result'
                    jsonl_file.write(json.dumps(result_dict) + '\n')

            # Last line: Write summary stats
            end_time = datetime.now()
            processing_time_seconds = (end_time - start_time).total_seconds()
            avg_time_per_image_ms = total_inference_time_ms / faces_detected if faces_detected > 0 else 0

            summary_stats_dict = FacialAnalysisProcessingService._calculate_summary_dict(results_for_summary)

            summary_line = {
                'type': 'summary',
                'summary_stats': summary_stats_dict,
                'processing_metadata': {
                    'processing_time_seconds': processing_time_seconds,
                    'avg_time_per_image_ms': avg_time_per_image_ms,
                    'faces_detected': faces_detected,
                    'failed': failed,
                    'total_processed': total_processed,
                    'completed_at': end_time.isoformat(),
                    'errors': failure_details
                }
            }
            jsonl_file.write(json.dumps(summary_line) + '\n')

        client.disconnect()

        # Determine success: should succeed if ANY images were successfully processed
        # Only fail if NO images were processed at all
        if total_processed == 0:
            processing_success = False
            status_message = 'Processing failed: No images were processed'
        elif faces_detected > 0:
            # Success if at least some faces were detected
            if failed > 0:
                processing_success = True
                status_message = f'Processed {total_processed} images: {faces_detected} successful, {failed} failed'
            else:
                processing_success = True
                status_message = f'Processed {total_processed} images successfully'
        else:
            # No faces detected in any images (but images were processed)
            processing_success = True
            status_message = f'Processed {total_processed} images (no faces detected in any images)'

        return ProcessingResult(
            success=processing_success,
            message=status_message,
            analysis_id=analysis_id,
            results_path=results_path,  # Path to JSONL results file
            total_processed=total_processed,
            faces_detected=faces_detected,
            failed=failed,
            processing_time_seconds=processing_time_seconds,
            avg_time_per_image_ms=avg_time_per_image_ms,
            summary_stats=summary_stats_dict,
            errors=failure_details or None
        )

    @staticmethod
    def _process_images_async(session_id: str, assessment_type: str, assessment_id: str,
                              analysis_id: str, grpc_host: str, grpc_port: int,
                              device: str, media_save_path: Optional[str]) -> ProcessingResult:
        """
        ASYNC BATCH PROCESSING VERSION (Non-blocking, better Flask performance)

        Process images using async batching:
        1. Send batches to gRPC asynchronously (non-blocking)
        2. Collect results as they complete
        3. Batch write to DB
        4. Sequential JSONL output
        """

        # This is the new async method - use asyncio.run() to execute
        # For now, returning a placeholder until full implementation
        # The old _process_images method is still available as fallback

        return ProcessingResult(
            success=False,
            message="Async processing not yet fully implemented - use synchronous method"
        )

    @staticmethod
    def _calculate_summary_dict(results: List[FacialAnalysisImageResult]) -> Dict[str, Any]:
        """Calculate summary statistics from analysis results (returns dict for Pydantic model)"""
        if not results:
            return {}

        # Count emotion distribution
        emotion_distribution = {}
        for result in results:
            emotion = result.analysis.facial_expression
            emotion_distribution[emotion] = emotion_distribution.get(emotion, 0) + 1

        # Find dominant emotion
        dominant_emotion = max(emotion_distribution.items(), key=lambda x: x[1])[0] if emotion_distribution else None

        # Calculate average AU activations
        total_au_activations = 0
        au_counts = {}

        for result in results:
            aus = result.analysis.action_units
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
    def get_processing_status(session_id: str, assessment_type: str) -> Optional[ProcessingStatus]:
        """Get processing status for a session assessment"""
        with get_session() as db:
            analysis = db.query(SessionFacialAnalysis).filter_by(
                session_id=session_id,
                assessment_type=assessment_type
            ).first()

            if not analysis:
                return None

            return ProcessingStatus(
                id=analysis.id,
                status=analysis.status,
                total_images_processed=analysis.total_images_processed,
                images_with_faces_detected=analysis.images_with_faces_detected,
                images_failed=analysis.images_failed,
                processing_time_seconds=analysis.processing_time_seconds,
                avg_time_per_image_ms=analysis.avg_time_per_image_ms,
                summary_stats=analysis.summary_stats,
                error_message=analysis.error_message,
                started_at=analysis.started_at.isoformat() if analysis.started_at else None,
                completed_at=analysis.completed_at.isoformat() if analysis.completed_at else None
            )
