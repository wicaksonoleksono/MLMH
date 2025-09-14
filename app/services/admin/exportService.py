# app/services/admin/exportService.py
import os
import json
import zipfile
from datetime import datetime
from typing import Dict, List, Any
from io import BytesIO
from flask import current_app
from ...db import get_session
from ...model.assessment.sessions import AssessmentSession, CameraCapture
from ...services.assessment.phqService import PHQResponseService
from ...services.assessment.llmService import LLMConversationService
from ...services.session.sessionTimingService import SessionTimingService


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
                zip_file.writestr('session_info.json', json.dumps(session_info, indent=2))
                
                # 2. PHQ responses
                if session.phq_completed_at:
                    phq_data = ExportService._get_phq_data(session_id)
                    zip_file.writestr('phq_responses.json', json.dumps(phq_data, indent=2))
                
                # 3. LLM conversation
                if session.llm_completed_at:
                    llm_data = ExportService._get_llm_data(session_id)
                    zip_file.writestr('llm_conversation.json', json.dumps(llm_data, indent=2))
                
                # 4. Camera captures
                ExportService._add_camera_captures(zip_file, session_id)
                
                # 5. Human-readable summary
                summary = ExportService._generate_summary(session, phq_data if session.phq_completed_at else None)
                zip_file.writestr('summary.txt', summary)

            zip_buffer.seek(0)
            return zip_buffer

    @staticmethod
    def _get_session_info(session: AssessmentSession) -> Dict[str, Any]:
        """Get basic session metadata"""
        return {
            'session_id': session.id,
            'user_id': session.user_id,
            'username': session.user.uname if session.user else 'Unknown',
            'session_number': session.session_number,
            'created_at': session.created_at.isoformat(),
            'completed_at': session.completed_at.isoformat() if session.completed_at else None,
            'status': session.status,
            'is_first': session.is_first,
            'phq_completed': session.phq_completed_at.isoformat() if session.phq_completed_at else None,
            'llm_completed': session.llm_completed_at.isoformat() if session.llm_completed_at else None,
            'consent_completed': session.consent_completed_at.isoformat() if session.consent_completed_at else None,
            'camera_completed': session.camera_completed,
            'failure_reason': session.failure_reason
        }

    @staticmethod
    def _get_phq_data(session_id: str) -> Dict[str, Any]:
        """Get PHQ responses in readable format using new JSON structure"""
        response_record = PHQResponseService.get_session_responses(session_id)
        total_score = PHQResponseService.calculate_session_score(session_id)
        
        # Group by category using new JSON structure
        phq_data = {
            'total_score': total_score,
            'max_possible_score': PHQResponseService.get_max_possible_score(session_id),
            'responses': {}
        }
        
        if response_record and response_record.responses:
            for question_id, response_data in response_record.responses.items():
                category = response_data.get('category_name', 'UNKNOWN')
                if category not in phq_data['responses']:
                    phq_data['responses'][category] = {}
                
                question_text = response_data.get('question_text', f'Question {question_id}')
                phq_data['responses'][category][question_text] = {
                    'response_text': response_data.get('response_text', ''),
                    'response_value': response_data.get('response_value', 0),
                    'response_time_ms': response_data.get('response_time_ms', None),
                    'session_time': response_data.get('session_time', None)  # Include unified session timing
                }
        
        return phq_data

    @staticmethod
    def _get_llm_data(session_id: str) -> Dict[str, Any]:
        """Get LLM conversation in readable format using new JSON structure"""
        conversation_turns = LLMConversationService.get_session_conversations(session_id)
        
        llm_data = {
            'total_conversations': len(conversation_turns),
            'conversations': []
        }
        
        for turn_data in conversation_turns:
            conv_data = {
                'turn_number': turn_data.get('turn_number'),
                'created_at': turn_data.get('created_at'),
                'ai_message': turn_data.get('ai_message'),
                'user_message': turn_data.get('user_message'),
                'user_message_length': turn_data.get('user_message_length'),
                'has_end_conversation': turn_data.get('has_end_conversation'),
                'ai_model_used': turn_data.get('ai_model_used'),
                'response_audio_path': turn_data.get('response_audio_path'),
                'transcription': turn_data.get('transcription'),
                'session_time': turn_data.get('session_time', None)  # Include unified session timing
            }
            
            llm_data['conversations'].append(conv_data)
        
        return llm_data

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
            
            # Create comprehensive metadata (only for linked captures)
            linked_captures = phq_captures + llm_captures
            metadata = {
                'total_captures': len(linked_captures),
                'phq_captures': len(phq_captures),
                'llm_captures': len(llm_captures),
                'unknown_captures_skipped': len(unknown_captures),
                'captures': []
            }
            
            # Add only linked captures to metadata
            for capture in linked_captures:
                # Determine assessment type and folder using new structure
                assessment_type = capture.capture_type
                folder_path = f"{assessment_type.lower()}/"
                
                # Add metadata for each filename in the JSON array
                for filename in capture.filenames:
                    capture_meta = {
                        'filename': filename,
                        'assessment_type': assessment_type,
                        'folder_path': folder_path,
                        'full_path': os.path.join(current_app.media_save, filename),
                        'zip_path': f'images/{folder_path}{filename}',
                        'timestamp': capture.created_at.isoformat(),
                        'capture_type': capture.capture_type,
                        'assessment_id': capture.assessment_id
                    }
                    
                    # Include session_time from capture metadata if available
                    if capture.capture_metadata and 'session_time' in capture.capture_metadata:
                        capture_meta['session_time'] = capture.capture_metadata['session_time']
                    else:
                        # Fallback: calculate session_time from timestamp for old captures
                        capture_meta['session_time'] = SessionTimingService.get_session_time(session_id, capture.created_at)
                    
                    metadata['captures'].append(capture_meta)
            
            # Add main metadata file
            zip_file.writestr('images/metadata.json', json.dumps(metadata, indent=2))
            
            # Add assessment-specific metadata files
            if phq_captures:
                phq_metadata = {
                    'assessment_type': 'PHQ',
                    'total_captures': len(phq_captures),
                    'captures': []
                }
                for capture in phq_captures:
                    for filename in capture.filenames:
                        capture_meta = {
                            'filename': filename,
                            'timestamp': capture.created_at.isoformat(),
                            'capture_type': capture.capture_type,
                            'assessment_id': capture.assessment_id
                        }
                        
                        # Include session_time from capture metadata if available
                        if capture.capture_metadata and 'session_time' in capture.capture_metadata:
                            capture_meta['session_time'] = capture.capture_metadata['session_time']
                        else:
                            # Fallback: calculate session_time from timestamp for old captures
                            capture_meta['session_time'] = SessionTimingService.get_session_time(session_id, capture.created_at)
                        
                        phq_metadata['captures'].append(capture_meta)
                zip_file.writestr('images/phq/metadata.json', json.dumps(phq_metadata, indent=2))
            
            if llm_captures:
                llm_metadata = {
                    'assessment_type': 'LLM',
                    'total_captures': len(llm_captures),
                    'captures': []
                }
                for capture in llm_captures:
                    for filename in capture.filenames:
                        capture_meta = {
                            'filename': filename,
                            'timestamp': capture.created_at.isoformat(),
                            'capture_type': capture.capture_type,
                            'assessment_id': capture.assessment_id
                        }
                        
                        # Include session_time from capture metadata if available
                        if capture.capture_metadata and 'session_time' in capture.capture_metadata:
                            capture_meta['session_time'] = capture.capture_metadata['session_time']
                        else:
                            # Fallback: calculate session_time from timestamp for old captures
                            capture_meta['session_time'] = SessionTimingService.get_session_time(session_id, capture.created_at)
                        
                        llm_metadata['captures'].append(capture_meta)
                zip_file.writestr('images/llm/metadata.json', json.dumps(llm_metadata, indent=2))

    @staticmethod
    def _generate_summary(session: AssessmentSession, phq_data: Dict = None) -> str:
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
- Total Score: {phq_data['total_score']}/{phq_data['max_possible_score']}
- Categories Assessed: {len(phq_data['responses'])}
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