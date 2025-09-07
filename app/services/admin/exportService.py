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
                    'response_time_ms': response_data.get('response_time_ms', None)
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
                'transcription': turn_data.get('transcription')
            }
            
            llm_data['conversations'].append(conv_data)
        
        return llm_data

    @staticmethod
    def _add_camera_captures(zip_file: zipfile.ZipFile, session_id: str):
        """Add camera captures to ZIP with PHQ/LLM organization"""
        with get_session() as db:
            captures = db.query(CameraCapture).filter_by(session_id=session_id).all()
            
            if not captures:
                print(f"📷 No camera captures found for session {session_id}")
                return
            
            # Organize captures by assessment type
            phq_captures = []
            llm_captures = []
            unknown_captures = []
            
            upload_path = current_app.media_save
            
            print(f"📷 Found {len(captures)} camera captures for session {session_id}")
            
            for capture in captures:
                print(f"📷 Processing capture: type={capture.capture_type}, assessment_id={capture.assessment_id}, filenames={capture.filenames}")
                
                # Determine assessment type using new model structure
                if capture.capture_type == 'PHQ':
                    assessment_type = "PHQ"
                    folder_path = "images/phq/"
                    phq_captures.append(capture)
                    
                    # Add all image files to PHQ folder (new model uses JSON array)
                    for filename in capture.filenames:
                        image_path = os.path.join(upload_path, filename)
                        print(f"📷 PHQ image path: {image_path}, exists: {os.path.exists(image_path)}")
                        if os.path.exists(image_path):
                            with open(image_path, 'rb') as img_file:
                                zip_file.writestr(f'{folder_path}{filename}', img_file.read())
                                print(f"📷 Added PHQ image: {filename}")
                                
                elif capture.capture_type == 'LLM':
                    assessment_type = "LLM"
                    folder_path = "images/llm/"
                    llm_captures.append(capture)
                    
                    # Add all image files to LLM folder (new model uses JSON array)
                    for filename in capture.filenames:
                        image_path = os.path.join(upload_path, filename)
                        print(f"📷 LLM image path: {image_path}, exists: {os.path.exists(image_path)}")
                        if os.path.exists(image_path):
                            with open(image_path, 'rb') as img_file:
                                zip_file.writestr(f'{folder_path}{filename}', img_file.read())
                                print(f"📷 Added LLM image: {filename}")
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
                    metadata['captures'].append({
                        'filename': filename,
                        'assessment_type': assessment_type,
                        'folder_path': folder_path,
                        'full_path': os.path.join(current_app.media_save, filename),
                        'zip_path': f'images/{folder_path}{filename}',
                        'timestamp': capture.created_at.isoformat(),
                        'capture_type': capture.capture_type,
                        'assessment_id': capture.assessment_id
                    })
            
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
                        phq_metadata['captures'].append({
                            'filename': filename,
                            'timestamp': capture.created_at.isoformat(),
                            'capture_type': capture.capture_type,
                            'assessment_id': capture.assessment_id
                        })
                zip_file.writestr('images/phq/metadata.json', json.dumps(phq_metadata, indent=2))
            
            if llm_captures:
                llm_metadata = {
                    'assessment_type': 'LLM',
                    'total_captures': len(llm_captures),
                    'captures': []
                }
                for capture in llm_captures:
                    for filename in capture.filenames:
                        llm_metadata['captures'].append({
                            'filename': filename,
                            'timestamp': capture.created_at.isoformat(),
                            'capture_type': capture.capture_type,
                            'assessment_id': capture.assessment_id
                        })
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
        """Export all sessions organized by session number into folders"""
        zip_buffer = BytesIO()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Get all completed sessions
            with get_session() as db:
                sessions = db.query(AssessmentSession).filter_by(status='COMPLETED').all()
                
                session_info_list = []
                session1_count = 0
                session2_count = 0
                
                for session in sessions:
                    try:
                        session_zip = ExportService.export_session(session.id)
                        # Get user info
                        if session.user:
                            username = session.user.uname
                            user_id = session.user_id
                            session_number = session.session_number
                            # Create a clean filename-safe version of the username
                            clean_username = "".join(c for c in username if c.isalnum() or c in (' ', '-', '_')).rstrip()
                            clean_username = clean_username.replace(' ', '_')
                            filename = f'user_{user_id}_{clean_username}_session{session_number}_{session.id}_{timestamp}.zip'
                            
                            # Organize by session number
                            if session_number == 1:
                                folder_path = f'session_1/{filename}'
                                session1_count += 1
                            elif session_number == 2:
                                folder_path = f'session_2/{filename}'
                                session2_count += 1
                            else:
                                folder_path = filename  # Fallback
                            
                            session_info_list.append({
                                'user_id': user_id,
                                'username': username,
                                'session_id': session.id,
                                'session_number': session_number,
                                'filename': filename,
                                'folder_path': folder_path
                            })
                            
                            zip_file.writestr(folder_path, session_zip.getvalue())
                        else:
                            # Handle sessions without user info
                            filename = f'session_{session.id}_{timestamp}.zip'
                            folder_path = f'unknown_user/{filename}'
                            session_info_list.append({
                                'user_id': 'Unknown',
                                'username': 'Unknown',
                                'session_id': session.id,
                                'session_number': 'Unknown',
                                'filename': filename,
                                'folder_path': folder_path
                            })
                            zip_file.writestr(folder_path, session_zip.getvalue())
                            
                    except Exception as e:
                        # Add error log for failed exports
                        error_msg = f"Failed to export session {session.id}: {str(e)}"
                        zip_file.writestr(f'ERROR_session_{session.id}.txt', error_msg)
                
                # Add summary
                summary = f"All Sessions Export Summary\n========================\nExported: {len(sessions)} sessions\nGenerated: {datetime.now().isoformat()}\n\nSession 1: {session1_count} sessions\nSession 2: {session2_count} sessions\n\nSession Details:\n"
                for info in session_info_list:
                    summary += f"- User {info['user_id']} ({info['username']}) - Session {info['session_number']} - File: {info['folder_path']}\n"
                
                zip_file.writestr('all_sessions_summary.txt', summary)
        
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
        """Generate all sessions export filename"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'all_sessions_export_{timestamp}.zip'