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
        """Get PHQ responses in readable format"""
        responses = PHQResponseService.get_session_responses(session_id)
        total_score = PHQResponseService.calculate_session_score(session_id)
        
        # Group by category
        phq_data = {
            'total_score': total_score,
            'max_possible_score': PHQResponseService.get_max_possible_score(session_id),
            'severity_level': PHQResponseService.get_severity_level(total_score),
            'responses': {}
        }
        
        for resp in responses:
            category = resp.category_name
            if category not in phq_data['responses']:
                phq_data['responses'][category] = {}
            
            phq_data['responses'][category][resp.question_text] = {
                'response_text': resp.response_text,
                'response_value': resp.response_value,
                'response_time_ms': resp.response_time_ms
            }
        
        return phq_data

    @staticmethod
    def _get_llm_data(session_id: str) -> Dict[str, Any]:
        """Get LLM conversation in readable format"""
        conversations = LLMConversationService.get_session_conversations(session_id)
        
        llm_data = {
            'total_conversations': len(conversations),
            'conversations': []
        }
        
        for conv in conversations:
            conv_data = {
                'conversation_id': conv.id,
                'turn_number': conv.turn_number,
                'created_at': conv.created_at.isoformat(),
                'ai_message': conv.ai_message,
                'user_message': conv.user_message,
                'user_message_length': conv.user_message_length,
                'has_end_conversation': conv.has_end_conversation,
                'ai_model_used': conv.ai_model_used,
                'response_audio_path': conv.response_audio_path,
                'transcription': conv.transcription
            }
            
            llm_data['conversations'].append(conv_data)
        
        return llm_data

    @staticmethod
    def _add_camera_captures(zip_file: zipfile.ZipFile, session_id: str):
        """Add camera captures to ZIP with PHQ/LLM organization"""
        with get_session() as db:
            captures = db.query(CameraCapture).filter_by(assessment_session_id=session_id).all()
            
            if not captures:
                return
            
            # Organize captures by assessment type
            phq_captures = []
            llm_captures = []
            unknown_captures = []
            
            upload_path = current_app.media_save
            
            for capture in captures:
                # Determine assessment type - SKIP unknown captures
                if capture.phq_response_id:
                    assessment_type = "PHQ"
                    folder_path = "images/phq/"
                    phq_captures.append(capture)
                    
                    # Add image file to PHQ folder
                    image_path = os.path.join(upload_path, capture.filename)
                    if os.path.exists(image_path):
                        with open(image_path, 'rb') as img_file:
                            zip_file.writestr(f'{folder_path}{capture.filename}', img_file.read())
                            
                elif capture.llm_conversation_id:
                    assessment_type = "LLM"
                    folder_path = "images/llm/"
                    llm_captures.append(capture)
                    
                    # Add image file to LLM folder
                    image_path = os.path.join(upload_path, capture.filename)
                    if os.path.exists(image_path):
                        with open(image_path, 'rb') as img_file:
                            zip_file.writestr(f'{folder_path}{capture.filename}', img_file.read())
                else:
                    # Skip unknown captures - don't add to ZIP
                    unknown_captures.append(capture)
                    print(f"⚠️ Skipping unknown capture {capture.filename} from export")
            
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
                # Determine assessment type and folder
                if capture.phq_response_id:
                    assessment_type = "PHQ"
                    folder_path = "phq/"
                elif capture.llm_conversation_id:
                    assessment_type = "LLM"
                    folder_path = "llm/"
                else:
                    assessment_type = "UNKNOWN"
                    folder_path = "unknown/"
                
                metadata['captures'].append({
                    'filename': capture.filename,
                    'assessment_type': assessment_type,
                    'folder_path': folder_path,
                    'full_path': os.path.join(current_app.media_save, capture.filename),
                    'zip_path': f'images/{folder_path}{capture.filename}',
                    'timestamp': capture.timestamp.isoformat(),
                    'trigger': capture.capture_trigger,
                    'file_size_bytes': capture.file_size_bytes,
                    'phq_response_id': capture.phq_response_id,
                    'llm_conversation_id': capture.llm_conversation_id
                })
            
            # Add main metadata file
            zip_file.writestr('images/metadata.json', json.dumps(metadata, indent=2))
            
            # Add assessment-specific metadata files
            if phq_captures:
                phq_metadata = {
                    'assessment_type': 'PHQ',
                    'total_captures': len(phq_captures),
                    'captures': [
                        {
                            'filename': capture.filename,
                            'timestamp': capture.timestamp.isoformat(),
                            'trigger': capture.capture_trigger,
                            'file_size_bytes': capture.file_size_bytes,
                            'phq_response_id': capture.phq_response_id
                        }
                        for capture in phq_captures
                    ]
                }
                zip_file.writestr('images/phq/metadata.json', json.dumps(phq_metadata, indent=2))
            
            if llm_captures:
                llm_metadata = {
                    'assessment_type': 'LLM',
                    'total_captures': len(llm_captures),
                    'captures': [
                        {
                            'filename': capture.filename,
                            'timestamp': capture.timestamp.isoformat(),
                            'trigger': capture.capture_trigger,
                            'file_size_bytes': capture.file_size_bytes,
                            'llm_conversation_id': capture.llm_conversation_id
                        }
                        for capture in llm_captures
                    ]
                }
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
- Severity Level: {phq_data['severity_level']}
- Categories Assessed: {len(phq_data['responses'])}
"""
        
        # Get image organization info
        with get_session() as db:
            captures = db.query(CameraCapture).filter_by(assessment_session_id=session.id).all()
            phq_images = len([c for c in captures if c.phq_response_id])
            llm_images = len([c for c in captures if c.llm_conversation_id])
            unknown_images = len([c for c in captures if not c.phq_response_id and not c.llm_conversation_id])
        
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