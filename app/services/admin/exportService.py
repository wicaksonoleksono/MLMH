# app/services/admin/exportService.py
import os
import zipfile
from datetime import datetime
from typing import List, Dict, Optional
from io import BytesIO
from flask import current_app
from ...db import get_session
from ...model.assessment.sessions import AssessmentSession, CameraCapture
from ...services.assessment.phqService import PHQResponseService
from ...services.assessment.llmService import LLMConversationService
from ...schemas.export import (
    SessionExportData,
    PHQExportData,
    PHQResponseItem,
    PHQTimingData,
    LLMExportData,
    LLMConversationTurn,
    LLMTimingData,
    CaptureMetadata,
    CaptureMetadataFull,
    CaptureTimingData,
    AssessmentCaptureMetadata,
    AllCapturesMetadata,
)


class ExportService:
    """Service for exporting session data as ZIP files"""

    @staticmethod
    def export_session(session_id: str) -> BytesIO:
        """Export single session as ZIP file"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")

            # Create ZIP in memory
            zip_buffer = BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # 1. Session info
                session_info = ExportService._get_session_info(session)
                zip_file.writestr('session_info.json', session_info.model_dump_json(indent=2))
                
                # 2. PHQ responses
                if session.phq_completed_at:
                    phq_data = ExportService._get_phq_data(session_id)
                    zip_file.writestr('phq_responses.json', phq_data.model_dump_json(indent=2))
                
                # 3. LLM conversation
                if session.llm_completed_at:
                    llm_data = ExportService._get_llm_data(session_id)
                    zip_file.writestr('llm_conversation.json', llm_data.model_dump_json(indent=2))
                
                # 4. Camera captures
                ExportService._add_camera_captures(zip_file, session_id)
                
                # 5. Human-readable summary
                phq_model = phq_data if session.phq_completed_at else None
                summary = ExportService._generate_summary(session, phq_model)
                zip_file.writestr('summary.txt', summary)

            zip_buffer.seek(0)
            return zip_buffer

    @staticmethod
    def _get_session_info(session: AssessmentSession) -> SessionExportData:
        """Get basic session metadata as Pydantic model"""
        return SessionExportData(
            session_id=session.id,
            user_id=session.user_id,
            username=session.user.uname if session.user else 'Unknown',
            session_number=session.session_number,
            created_at=session.created_at.isoformat(),
            completed_at=session.completed_at.isoformat() if session.completed_at else None,
            status=session.status,
            is_first=session.is_first,
            phq_completed=session.phq_completed_at.isoformat() if session.phq_completed_at else None,
            llm_completed=session.llm_completed_at.isoformat() if session.llm_completed_at else None,
            consent_completed=session.consent_completed_at.isoformat() if session.consent_completed_at else None,
            camera_completed=session.camera_completed,
            failure_reason=session.failure_reason
        )

    @staticmethod
    def _get_phq_data(session_id: str) -> PHQExportData:
        """Get PHQ responses in readable format using new JSON structure as Pydantic model"""
        response_record = PHQResponseService.get_session_responses(session_id)
        total_score = PHQResponseService.calculate_session_score(session_id)

        # Group by category using new JSON structure
        responses: Dict[str, Dict[str, PHQResponseItem]] = {}

        if response_record and response_record.responses:
            for question_id, response_data in response_record.responses.items():
                category = response_data.get('category_name', 'UNKNOWN')
                if category not in responses:
                    responses[category] = {}

                question_text = response_data.get('question_text', f'Question {question_id}')

                # Create timing data if available
                timing_dict = response_data.get('timing', {})
                timing_data = PHQTimingData(**timing_dict) if timing_dict else None

                responses[category][question_text] = PHQResponseItem(
                    response_text=response_data.get('response_text', ''),
                    response_value=response_data.get('response_value', 0),
                    response_time_ms=response_data.get('response_time_ms', None),
                    timing=timing_data
                )

        return PHQExportData(
            total_score=total_score,
            max_possible_score=PHQResponseService.get_max_possible_score(session_id),
            responses=responses
        )

    @staticmethod
    def _get_llm_data(session_id: str) -> LLMExportData:
        """Get LLM conversation in readable format using new JSON structure as Pydantic model"""
        conversation_turns = LLMConversationService.get_session_conversations(session_id)

        conversations: List[LLMConversationTurn] = []

        for turn_data in conversation_turns:
            # Create timing data - may be empty dict {}
            user_timing_dict = turn_data.get('user_timing', {})
            user_timing = LLMTimingData(**user_timing_dict)

            ai_timing_dict = turn_data.get('ai_timing', {})
            ai_timing = LLMTimingData(**ai_timing_dict)

            conversations.append(LLMConversationTurn(
                turn_number=turn_data.get('turn_number'),
                created_at=turn_data.get('created_at'),
                ai_message=turn_data.get('ai_message'),
                user_message=turn_data.get('user_message'),
                user_message_length=turn_data.get('user_message_length'),
                has_end_conversation=turn_data.get('has_end_conversation'),
                ai_model_used=turn_data.get('ai_model_used'),
                user_timing=user_timing,
                ai_timing=ai_timing
            ))

        return LLMExportData(
            total_conversations=len(conversation_turns),
            conversations=conversations
        )

    @staticmethod
    def _add_camera_captures(zip_file: zipfile.ZipFile, session_id: str):
        """Add camera captures to ZIP with PHQ/LLM organization"""
        with get_session() as db:
            captures = db.query(CameraCapture).filter_by(session_id=session_id).all()
            
            if not captures:
                print(f" No camera captures found for session {session_id}")
                return
            
            # Organize captures by assessment type
            phq_captures = []
            llm_captures = []
            unknown_captures = []
            
            upload_path = current_app.media_save
            
            print(f" Found {len(captures)} camera captures for session {session_id}")
            
            for capture in captures:
                print(f" Processing capture: type={capture.capture_type}, assessment_id={capture.assessment_id}, filenames={capture.filenames}")
                
                # Determine assessment type using new model structure
                if capture.capture_type == 'PHQ':
                    assessment_type = "PHQ"
                    folder_path = "images/phq/"
                    phq_captures.append(capture)
                    
                    # Add all image files to PHQ folder (new model uses JSON array)
                    for filename in capture.filenames:
                        image_path = os.path.join(upload_path, filename)
                        if os.path.exists(image_path):
                            with open(image_path, 'rb') as img_file:
                                zip_file.writestr(f'{folder_path}{filename}', img_file.read())
                                
                elif capture.capture_type == 'LLM':
                    assessment_type = "LLM"
                    folder_path = "images/llm/"
                    llm_captures.append(capture)
                    
                    # Add all image files to LLM folder (new model uses JSON array)
                    for filename in capture.filenames:
                        image_path = os.path.join(upload_path, filename)
                        if os.path.exists(image_path):
                            with open(image_path, 'rb') as img_file:
                                zip_file.writestr(f'{folder_path}{filename}', img_file.read())
                else:
                    # Skip general/unknown captures - don't add to ZIP
                    unknown_captures.append(capture)
                    print(f"⚠️ Skipping {capture.capture_type} capture {capture.filenames} from export")
            
            # Create comprehensive metadata using Pydantic models
            linked_captures = phq_captures + llm_captures
            all_capture_metadata: List[CaptureMetadataFull] = []

            # Add only linked captures to metadata
            for capture in linked_captures:
                # Determine assessment type and folder using new structure
                assessment_type = capture.capture_type
                folder_path = f"{assessment_type.lower()}/"

                # Add metadata for each filename in the JSON array
                for filename in capture.filenames:
                    # Extract timing data if available
                    timing_data = None
                    capture_timestamp = None

                    if capture.capture_metadata and 'capture_history' in capture.capture_metadata:
                        capture_history = capture.capture_metadata['capture_history']
                        # Find the entry for this filename
                        for entry in capture_history:
                            if entry.get('filename') == filename and 'timing' in entry:
                                timing_dict = entry['timing']
                                timing_data = CaptureTimingData(**timing_dict)
                                break

                    # For old captures without timing, use the capture timestamp
                    if not timing_data:
                        capture_timestamp = capture.created_at.isoformat()

                    capture_meta = CaptureMetadataFull(
                        filename=filename,
                        assessment_type=assessment_type,
                        folder_path=folder_path,
                        full_path=os.path.join(current_app.media_save, filename),
                        zip_path=f'images/{folder_path}{filename}',
                        timestamp=capture.created_at.isoformat(),
                        capture_type=capture.capture_type,
                        assessment_id=capture.assessment_id,
                        assessment_timing=timing_data,
                        capture_timestamp=capture_timestamp
                    )

                    all_capture_metadata.append(capture_meta)

            # Create AllCapturesMetadata Pydantic model
            metadata_model = AllCapturesMetadata(
                total_captures=len(linked_captures),
                phq_captures=len(phq_captures),
                llm_captures=len(llm_captures),
                unknown_captures_skipped=len(unknown_captures),
                captures=all_capture_metadata
            )

            # Add main metadata file
            zip_file.writestr('images/metadata.json', metadata_model.model_dump_json(indent=2))
            
            # Add assessment-specific metadata files using Pydantic models
            if phq_captures:
                phq_capture_list: List[CaptureMetadata] = []

                for capture in phq_captures:
                    for filename in capture.filenames:
                        # Extract timing data if available
                        timing_data = None
                        capture_timestamp = None

                        if capture.capture_metadata and 'capture_history' in capture.capture_metadata:
                            capture_history = capture.capture_metadata['capture_history']
                            for entry in capture_history:
                                if entry.get('filename') == filename and 'timing' in entry:
                                    timing_dict = entry['timing']
                                    timing_data = CaptureTimingData(**timing_dict)
                                    break

                        # For old captures without timing, use the capture timestamp
                        if not timing_data:
                            capture_timestamp = capture.created_at.isoformat()

                        capture_meta = CaptureMetadata(
                            filename=filename,
                            timestamp=capture.created_at.isoformat(),
                            capture_type=capture.capture_type,
                            assessment_id=capture.assessment_id,
                            assessment_timing=timing_data,
                            capture_timestamp=capture_timestamp
                        )

                        phq_capture_list.append(capture_meta)

                phq_metadata_model = AssessmentCaptureMetadata(
                    assessment_type='PHQ',
                    total_captures=len(phq_captures),
                    captures=phq_capture_list
                )
                zip_file.writestr('images/phq/metadata.json', phq_metadata_model.model_dump_json(indent=2))
            
            if llm_captures:
                llm_capture_list: List[CaptureMetadata] = []

                for capture in llm_captures:
                    for filename in capture.filenames:
                        # Extract timing data if available
                        timing_data = None
                        capture_timestamp = None

                        if capture.capture_metadata and 'capture_history' in capture.capture_metadata:
                            capture_history = capture.capture_metadata['capture_history']
                            for entry in capture_history:
                                if entry.get('filename') == filename and 'timing' in entry:
                                    timing_dict = entry['timing']
                                    timing_data = CaptureTimingData(**timing_dict)
                                    break

                        # For old captures without timing, use the capture timestamp
                        if not timing_data:
                            capture_timestamp = capture.created_at.isoformat()

                        capture_meta = CaptureMetadata(
                            filename=filename,
                            timestamp=capture.created_at.isoformat(),
                            capture_type=capture.capture_type,
                            assessment_id=capture.assessment_id,
                            assessment_timing=timing_data,
                            capture_timestamp=capture_timestamp
                        )

                        llm_capture_list.append(capture_meta)

                llm_metadata_model = AssessmentCaptureMetadata(
                    assessment_type='LLM',
                    total_captures=len(llm_captures),
                    captures=llm_capture_list
                )
                zip_file.writestr('images/llm/metadata.json', llm_metadata_model.model_dump_json(indent=2))

    @staticmethod
    def _generate_summary(session: AssessmentSession, phq_data: Optional[PHQExportData] = None) -> str:
        """Generate human-readable summary"""
        summary = f"""
MENTAL HEALTH ASSESSMENT EXPORT
================================

Session Information:
- Session ID: {session.id}
- User: {session.user.uname if session.user else 'Unknown'} (ID: {session.user_id})
- Session Number: {session.session_number}
- Created: {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}
- Status: {session.status}
- Assessment Order: {session.is_first} first

Assessment Completion:
- PHQ Assessment: {'✓ Completed' if session.phq_completed_at else '✗ Not completed'}
- LLM Assessment: {'✓ Completed' if session.llm_completed_at else '✗ Not completed'}
- Camera Check: {'✓ Completed' if session.camera_completed else '✗ Not completed'}
- Consent: {'✓ Completed' if session.consent_completed_at else '✗ Not completed'}
"""

        if phq_data:
            summary += f"""
PHQ Results Summary:
- Total Score: {phq_data.total_score}/{phq_data.max_possible_score}
- Categories Assessed: {len(phq_data.responses)}
"""
        
        # Get image organization info
        with get_session() as db:
            captures = db.query(CameraCapture).filter_by(session_id=session.id).all()
            phq_images = sum(len(c.filenames) for c in captures if c.capture_type == 'PHQ')
            llm_images = sum(len(c.filenames) for c in captures if c.capture_type == 'LLM')
            unknown_images = sum(len(c.filenames) for c in captures if c.capture_type == 'GENERAL')
        
        summary += f"""
Export Details:
- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Files Included: session_info.json, phq_responses.json, llm_conversation.json
- Images Organization:
  * PHQ Assessment Images: {phq_images} files in images/phq/
  * LLM Assessment Images: {llm_images} files in images/llm/
  * Unknown Images Skipped: {unknown_images} (unlinked captures excluded from export)
  * Total Images Exported: {phq_images + llm_images} files
  * Metadata: images/metadata.json (main), images/phq/metadata.json, images/llm/metadata.json
- Format: ZIP archive with organized JSON data and assessment-specific image folders

Note: This export contains sensitive mental health data. Handle with appropriate confidentiality.
"""
        
        return summary.strip()

    @staticmethod
    def export_bulk_sessions(session_ids: List[str]) -> BytesIO:
        """Export multiple sessions organized by session number (S1/S2 folders)"""
        zip_buffer = BytesIO()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            session_info_list = []
            session1_count = 0
            session2_count = 0
            
            for session_id in session_ids:
                try:
                    session_zip = ExportService.export_session(session_id)
                    # Get session info for the summary
                    with get_session() as db:
                        session = db.query(AssessmentSession).filter_by(id=session_id).first()
                        if session and session.user:
                            username = session.user.uname
                            user_id = session.user_id
                            session_number = session.session_number
                            # Create a clean filename-safe version of the username
                            clean_username = "".join(c for c in username if c.isalnum() or c in (' ', '-', '_')).rstrip()
                            clean_username = clean_username.replace(' ', '_')
                            filename = f'user_{user_id}_{clean_username}_session{session_number}_{session_id}.zip'
                            
                            # Organize by session number into folders
                            if session_number == 1:
                                folder_path = f'session_1/{filename}'
                                session1_count += 1
                            elif session_number == 2:
                                folder_path = f'session_2/{filename}'
                                session2_count += 1
                            else:
                                folder_path = f'unknown_session/{filename}'  # Fallback
                                
                            session_info_list.append({
                                'user_id': user_id,
                                'username': username,
                                'session_id': session_id,
                                'session_number': session_number,
                                'filename': filename,
                                'folder_path': folder_path
                            })
                        else:
                            filename = f'session_{session_id}_{timestamp}.zip'
                            folder_path = f'unknown_user/{filename}'
                            session_info_list.append({
                                'user_id': 'Unknown',
                                'username': 'Unknown',
                                'session_id': session_id,
                                'session_number': 'Unknown',
                                'filename': filename,
                                'folder_path': folder_path
                            })
                    
                    zip_file.writestr(folder_path, session_zip.getvalue())
                except Exception as e:
                    # Add error log for failed exports
                    error_msg = f"Failed to export session {session_id}: {str(e)}"
                    zip_file.writestr(f'ERROR_session_{session_id}.txt', error_msg)
            
            # Add bulk summary with session separation info
            summary = f"Bulk Export Summary\n==================\nExported: {len(session_ids)} sessions\nGenerated: {datetime.now().isoformat()}\n\nSession 1: {session1_count} sessions\nSession 2: {session2_count} sessions\n\nSession Details:\n"
            for info in session_info_list:
                summary += f"- User {info['user_id']} ({info['username']}) - Session {info['session_number']} - File: {info['folder_path']}\n"
            
            zip_file.writestr('bulk_summary.txt', summary)
        
        zip_buffer.seek(0)
        return zip_buffer

    @staticmethod
    def export_sessions_by_session_number() -> BytesIO:
        """Export all sessions organized by completion status (completed/incomplete users)"""
        zip_buffer = BytesIO()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Use StatsService to get organized user data
            from .statsService import StatsService
            user_data = StatsService.get_all_user_sessions_for_export()
            
            session_info_list = []
            completed_count = 0
            incomplete_count = 0
            
            # Process completed users (both sessions completed)
            for user_info in user_data['completed']:
                user = user_info['user']
                sessions = user_info['sessions']
                
                try:
                    username = user.uname
                    user_id = user.id
                    clean_username = "".join(c for c in username if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    clean_username = clean_username.replace(' ', '_')
                    
                    # Export each session for this completed user
                    for session in sessions:
                        session_zip = ExportService.export_session(session.id)
                        filename = f'user_{user_id}_{clean_username}_session{session.session_number}_{session.id}_{timestamp}.zip'
                        folder_path = f'completed/{filename}'
                        
                        session_info_list.append({
                            'user_id': user_id,
                            'username': username,
                            'session_id': session.id,
                            'session_number': session.session_number,
                            'filename': filename,
                            'folder_path': folder_path,
                            'completion_status': 'completed'
                        })
                        
                        zip_file.writestr(folder_path, session_zip.getvalue())
                    
                    completed_count += 1
                    
                except Exception as e:
                    error_msg = f"Failed to export completed user {user.id} sessions: {str(e)}"
                    zip_file.writestr(f'completed/ERROR_user_{user.id}.txt', error_msg)
            
            # Process incomplete users (only session 1 completed)
            for user_info in user_data['incomplete']:
                user = user_info['user']
                sessions = user_info['sessions']
                
                try:
                    username = user.uname
                    user_id = user.id
                    clean_username = "".join(c for c in username if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    clean_username = clean_username.replace(' ', '_')
                    
                    # Export session 1 for this incomplete user
                    for session in sessions:
                        if session.status == 'COMPLETED':  # Only export completed sessions
                            session_zip = ExportService.export_session(session.id)
                            filename = f'user_{user_id}_{clean_username}_session{session.session_number}_{session.id}_{timestamp}.zip'
                            folder_path = f'incomplete/{filename}'
                            
                            session_info_list.append({
                                'user_id': user_id,
                                'username': username,
                                'session_id': session.id,
                                'session_number': session.session_number,
                                'filename': filename,
                                'folder_path': folder_path,
                                'completion_status': 'incomplete'
                            })
                            
                            zip_file.writestr(folder_path, session_zip.getvalue())
                    
                    incomplete_count += 1
                    
                except Exception as e:
                    error_msg = f"Failed to export incomplete user {user.id} sessions: {str(e)}"
                    zip_file.writestr(f'incomplete/ERROR_user_{user.id}.txt', error_msg)
            
            # Add comprehensive summary
            summary = f"""All Sessions Export Summary (Completion-Based)
=============================================
Exported: {len(session_info_list)} sessions from {completed_count + incomplete_count} users
Generated: {datetime.now().isoformat()}

Organization:
- Completed Users: {completed_count} users (both Session 1 & 2 completed)
- Incomplete Users: {incomplete_count} users (only Session 1 completed)

Total Sessions by Number:
- Session 1: {len([s for s in session_info_list if s['session_number'] == 1])} sessions
- Session 2: {len([s for s in session_info_list if s['session_number'] == 2])} sessions

Session Details:
"""
            
            # Group by completion status for better readability
            completed_sessions = [s for s in session_info_list if s['completion_status'] == 'completed']
            incomplete_sessions = [s for s in session_info_list if s['completion_status'] == 'incomplete']
            
            if completed_sessions:
                summary += "\nCOMPLETED USERS (Both Sessions):\n" + "-" * 35 + "\n"
                for info in completed_sessions:
                    summary += f"- User {info['user_id']} ({info['username']}) - Session {info['session_number']} - {info['filename']}\n"
            
            if incomplete_sessions:
                summary += "\nINCOMPLETE USERS (Session 1 Only):\n" + "-" * 36 + "\n"
                for info in incomplete_sessions:
                    summary += f"- User {info['user_id']} ({info['username']}) - Session {info['session_number']} - {info['filename']}\n"
            
            zip_file.writestr('export_summary.txt', summary)
        
        zip_buffer.seek(0)
        return zip_buffer

    @staticmethod
    def get_export_filename(session_id: str) -> str:
        """Generate export filename with user identification and session number"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if session and session.user:
                username = session.user.uname
                user_id = session.user_id
                session_number = session.session_number
                # Create a clean filename-safe version of the username
                clean_username = "".join(c for c in username if c.isalnum() or c in (' ', '-', '_')).rstrip()
                clean_username = clean_username.replace(' ', '_')
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                return f'user_{user_id}_{clean_username}_session{session_number}_{session_id}_{timestamp}.zip'
            else:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                return f'session_{session_id}_{timestamp}.zip'

    @staticmethod
    def get_bulk_export_filename() -> str:
        """Generate bulk export filename"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'bulk_sessions_export_{timestamp}.zip'

    @staticmethod
    def get_all_sessions_export_filename() -> str:
        """Generate filename for all sessions export (completion-based organization)"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'sessions_by_completion_status_{timestamp}.zip'

    # ============= FACIAL ANALYSIS EXPORT METHODS =============

    @staticmethod
    def export_session_with_facial_analysis(session_id: str) -> BytesIO:
        """Export session with PHQ data, LLM data, and JSONL files (NO images)"""
        from ...model.assessment.facial_analysis import SessionFacialAnalysis

        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")

            # Get facial analysis records
            phq_analysis = db.query(SessionFacialAnalysis).filter_by(
                session_id=session_id,
                assessment_type='PHQ'
            ).first()

            llm_analysis = db.query(SessionFacialAnalysis).filter_by(
                session_id=session_id,
                assessment_type='LLM'
            ).first()

            # Check if both are completed
            if not (phq_analysis and phq_analysis.status == 'completed' and
                    llm_analysis and llm_analysis.status == 'completed'):
                raise ValueError("Both PHQ and LLM facial analysis must be completed")

            # Create ZIP in memory
            zip_buffer = BytesIO()

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # 1. Session info
                session_info = ExportService._get_session_info(session)
                zip_file.writestr('session_info.json', session_info.model_dump_json(indent=2))

                # 2. PHQ responses
                if session.phq_completed_at:
                    phq_data = ExportService._get_phq_data(session_id)
                    zip_file.writestr('phq_responses.json', phq_data.model_dump_json(indent=2))

                # 3. LLM conversation
                if session.llm_completed_at:
                    llm_data = ExportService._get_llm_data(session_id)
                    zip_file.writestr('llm_conversation.json', llm_data.model_dump_json(indent=2))

                # 4. Add JSONL files
                upload_path = current_app.media_save

                # Add PHQ JSONL
                phq_jsonl_path = os.path.join(upload_path, phq_analysis.jsonl_file_path)
                if os.path.exists(phq_jsonl_path):
                    with open(phq_jsonl_path, 'r') as f:
                        zip_file.writestr('facial_analysis/phq_analysis.jsonl', f.read())

                # Add LLM JSONL
                llm_jsonl_path = os.path.join(upload_path, llm_analysis.jsonl_file_path)
                if os.path.exists(llm_jsonl_path):
                    with open(llm_jsonl_path, 'r') as f:
                        zip_file.writestr('facial_analysis/llm_analysis.jsonl', f.read())

                # 5. Add facial analysis metadata
                facial_metadata = {
                    'phq_analysis': {
                        'status': phq_analysis.status,
                        'total_images_processed': phq_analysis.total_images_processed,
                        'images_with_faces_detected': phq_analysis.images_with_faces_detected,
                        'images_failed': phq_analysis.images_failed,
                        'processing_time_seconds': phq_analysis.processing_time_seconds,
                        'avg_time_per_image_ms': phq_analysis.avg_time_per_image_ms,
                        'summary_stats': phq_analysis.summary_stats,
                        'started_at': phq_analysis.started_at.isoformat() if phq_analysis.started_at else None,
                        'completed_at': phq_analysis.completed_at.isoformat() if phq_analysis.completed_at else None
                    },
                    'llm_analysis': {
                        'status': llm_analysis.status,
                        'total_images_processed': llm_analysis.total_images_processed,
                        'images_with_faces_detected': llm_analysis.images_with_faces_detected,
                        'images_failed': llm_analysis.images_failed,
                        'processing_time_seconds': llm_analysis.processing_time_seconds,
                        'avg_time_per_image_ms': llm_analysis.avg_time_per_image_ms,
                        'summary_stats': llm_analysis.summary_stats,
                        'started_at': llm_analysis.started_at.isoformat() if llm_analysis.started_at else None,
                        'completed_at': llm_analysis.completed_at.isoformat() if llm_analysis.completed_at else None
                    }
                }
                import json
                zip_file.writestr('facial_analysis/metadata.json', json.dumps(facial_metadata, indent=2))

                # 6. Generate summary
                phq_model = phq_data if session.phq_completed_at else None
                summary = ExportService._generate_facial_analysis_summary(
                    session, phq_analysis, llm_analysis, phq_model
                )
                zip_file.writestr('summary.txt', summary)

            zip_buffer.seek(0)
            return zip_buffer

    @staticmethod
    def _generate_facial_analysis_summary(session: AssessmentSession,
                                          phq_analysis, llm_analysis, phq_data: Optional[PHQExportData] = None) -> str:
        """Generate human-readable summary for facial analysis export"""
        summary = f"""
FACIAL ANALYSIS EXPORT
======================

Session Information:
- Session ID: {session.id}
- User: {session.user.uname if session.user else 'Unknown'} (ID: {session.user_id})
- Session Number: {session.session_number}
- Created: {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}
- Status: {session.status}
- Assessment Order: {session.is_first} first

Assessment Completion:
- PHQ Assessment: {'✓ Completed' if session.phq_completed_at else '✗ Not completed'}
- LLM Assessment: {'✓ Completed' if session.llm_completed_at else '✗ Not completed'}
"""

        if phq_data:
            summary += f"""
PHQ Results Summary:
- Total Score: {phq_data.total_score}/{phq_data.max_possible_score}
- Categories Assessed: {len(phq_data.responses)}
"""

        summary += f"""
Facial Analysis Results:
------------------------

PHQ Assessment Analysis:
- Status: {phq_analysis.status}
- Total Images Processed: {phq_analysis.total_images_processed}
- Faces Detected: {phq_analysis.images_with_faces_detected}
- Failed: {phq_analysis.images_failed}
- Processing Time: {phq_analysis.processing_time_seconds:.2f}s
- Avg Time per Image: {phq_analysis.avg_time_per_image_ms:.2f}ms
- Dominant Emotion: {phq_analysis.get_dominant_emotion() or 'N/A'}

LLM Assessment Analysis:
- Status: {llm_analysis.status}
- Total Images Processed: {llm_analysis.total_images_processed}
- Faces Detected: {llm_analysis.images_with_faces_detected}
- Failed: {llm_analysis.images_failed}
- Processing Time: {llm_analysis.processing_time_seconds:.2f}s
- Avg Time per Image: {llm_analysis.avg_time_per_image_ms:.2f}ms
- Dominant Emotion: {llm_analysis.get_dominant_emotion() or 'N/A'}

Export Contents:
----------------
- session_info.json - Session metadata
- phq_responses.json - PHQ assessment responses
- llm_conversation.json - LLM conversation history
- facial_analysis/phq_analysis.jsonl - PHQ facial analysis results (frame-by-frame)
- facial_analysis/llm_analysis.jsonl - LLM facial analysis results (frame-by-frame)
- facial_analysis/metadata.json - Processing metadata and statistics

NOTE: This export contains PHQ/LLM data + JSONL files. Images are NOT included.
      For images, use the regular User Sessions export.

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Note: This export contains sensitive mental health data. Handle with appropriate confidentiality.
"""
        return summary.strip()

    @staticmethod
    def export_bulk_facial_analysis(session_ids: List[str]) -> BytesIO:
        """Export multiple sessions with facial analysis - flat structure with JSONL files"""
        from ...model.assessment.facial_analysis import SessionFacialAnalysis

        zip_buffer = BytesIO()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            session_info_list = []
            session1_count = 0
            session2_count = 0

            for session_id in session_ids:
                try:
                    with get_session() as db:
                        session = db.query(AssessmentSession).filter_by(id=session_id).first()
                        if not session:
                            raise ValueError(f"Session {session_id} not found")

                        # Get facial analysis records
                        phq_analysis = db.query(SessionFacialAnalysis).filter_by(
                            session_id=session_id,
                            assessment_type='PHQ'
                        ).first()
                        llm_analysis = db.query(SessionFacialAnalysis).filter_by(
                            session_id=session_id,
                            assessment_type='LLM'
                        ).first()

                        # Check if both are completed
                        if not (phq_analysis and phq_analysis.status == 'completed' and
                                llm_analysis and llm_analysis.status == 'completed'):
                            raise ValueError("Both PHQ and LLM facial analysis must be completed")

                        # Build folder name
                        username = session.user.uname if session.user else 'unknown'
                        user_id = session.user_id
                        session_number = session.session_number
                        is_first = session.is_first  # 'phq' or 'llm'

                        clean_username = "".join(c for c in username if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        clean_username = clean_username.replace(' ', '_')

                        folder_name = f'user_{user_id}_{clean_username}_session{session_number}'

                        # Count sessions
                        if session_number == 1:
                            session1_count += 1
                        elif session_number == 2:
                            session2_count += 1

                        # 1. Session info
                        session_info = ExportService._get_session_info(session)
                        zip_file.writestr(f'{folder_name}/session_info.json', session_info.model_dump_json(indent=2))

                        # 2. PHQ responses
                        if session.phq_completed_at:
                            phq_data = ExportService._get_phq_data(session_id)
                            zip_file.writestr(f'{folder_name}/phq_responses.json', phq_data.model_dump_json(indent=2))

                        # 3. LLM conversation
                        if session.llm_completed_at:
                            llm_data = ExportService._get_llm_data(session_id)
                            zip_file.writestr(f'{folder_name}/llm_conversation.json', llm_data.model_dump_json(indent=2))

                        # 4. Add JSONL files (flat, no nested folders)
                        upload_path = current_app.media_save

                        # Add PHQ JSONL
                        phq_jsonl_path = os.path.join(upload_path, phq_analysis.jsonl_file_path)
                        if os.path.exists(phq_jsonl_path):
                            with open(phq_jsonl_path, 'r') as f:
                                zip_file.writestr(f'{folder_name}/phq_analysis.jsonl', f.read())

                        # Add LLM JSONL
                        llm_jsonl_path = os.path.join(upload_path, llm_analysis.jsonl_file_path)
                        if os.path.exists(llm_jsonl_path):
                            with open(llm_jsonl_path, 'r') as f:
                                zip_file.writestr(f'{folder_name}/llm_analysis.jsonl', f.read())

                        # 5. Add facial analysis metadata
                        facial_metadata = {
                            'phq_analysis': {
                                'status': phq_analysis.status,
                                'total_images_processed': phq_analysis.total_images_processed,
                                'images_with_faces_detected': phq_analysis.images_with_faces_detected,
                                'images_failed': phq_analysis.images_failed,
                                'processing_time_seconds': phq_analysis.processing_time_seconds,
                                'avg_time_per_image_ms': phq_analysis.avg_time_per_image_ms,
                                'summary_stats': phq_analysis.summary_stats,
                                'started_at': phq_analysis.started_at.isoformat() if phq_analysis.started_at else None,
                                'completed_at': phq_analysis.completed_at.isoformat() if phq_analysis.completed_at else None
                            },
                            'llm_analysis': {
                                'status': llm_analysis.status,
                                'total_images_processed': llm_analysis.total_images_processed,
                                'images_with_faces_detected': llm_analysis.images_with_faces_detected,
                                'images_failed': llm_analysis.images_failed,
                                'processing_time_seconds': llm_analysis.processing_time_seconds,
                                'avg_time_per_image_ms': llm_analysis.avg_time_per_image_ms,
                                'summary_stats': llm_analysis.summary_stats,
                                'started_at': llm_analysis.started_at.isoformat() if llm_analysis.started_at else None,
                                'completed_at': llm_analysis.completed_at.isoformat() if llm_analysis.completed_at else None
                            }
                        }
                        import json
                        zip_file.writestr(f'{folder_name}/metadata.json', json.dumps(facial_metadata, indent=2))

                        # 6. Generate summary
                        phq_model = phq_data if session.phq_completed_at else None
                        summary = ExportService._generate_facial_analysis_summary(
                            session, phq_analysis, llm_analysis, phq_model
                        )
                        zip_file.writestr(f'{folder_name}/summary.txt', summary)

                        session_info_list.append({
                            'user_id': user_id,
                            'username': username,
                            'session_id': session_id,
                            'session_number': session_number,
                            'is_first': is_first,
                            'folder_name': folder_name
                        })

                except Exception as e:
                    # Add error log for failed exports
                    error_msg = f"Failed to export facial analysis for session {session_id}: {str(e)}\n"
                    import traceback
                    error_msg += traceback.format_exc()
                    zip_file.writestr(f'ERROR_session_{session_id}.txt', error_msg)

            # Add bulk summary
            summary = f"""Bulk Facial Analysis Export Summary
====================================
Exported: {len(session_info_list)} sessions successfully (out of {len(session_ids)} requested)
Generated: {datetime.now().isoformat()}

Session 1: {session1_count} sessions
Session 2: {session2_count} sessions

Session Details:
"""
            for info in session_info_list:
                summary += f"- User {info['user_id']} ({info['username']}) - Session {info['session_number']} - Assessment Order: {info['is_first'].upper()} first - Folder: {info['folder_name']}/\n"

            zip_file.writestr('bulk_summary.txt', summary)

        zip_buffer.seek(0)
        return zip_buffer

    @staticmethod
    def get_facial_analysis_export_filename(session_id: str) -> str:
        """Generate export filename for facial analysis export"""
        with get_session() as db:
            session = db.query(AssessmentSession).filter_by(id=session_id).first()
            if session and session.user:
                username = session.user.uname
                user_id = session.user_id
                session_number = session.session_number
                clean_username = "".join(c for c in username if c.isalnum() or c in (' ', '-', '_')).rstrip()
                clean_username = clean_username.replace(' ', '_')
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                return f'user_{user_id}_{clean_username}_session{session_number}_{session_id}_facial_analysis_{timestamp}.zip'
            else:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                return f'session_{session_id}_facial_analysis_{timestamp}.zip'

    @staticmethod
    def get_bulk_facial_analysis_export_filename() -> str:
        """Generate bulk facial analysis export filename"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'bulk_facial_analysis_export_{timestamp}.zip'