# app/routes/admin/export_routes.py
from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
from ...decorators import admin_required, raw_response, api_response
from ...services.admin.exportService import ExportService
from ...services.session.sessionManager import SessionManager

export_bp = Blueprint('export', __name__, url_prefix='/admin/export')


@export_bp.route('/session/<session_id>')
@login_required
@admin_required
@raw_response
def export_session(session_id):
    """Export single session as ZIP download"""
    try:
        zip_buffer = ExportService.export_session(session_id)
        filename = ExportService.get_export_filename(session_id)
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Export failed: {str(e)}"}), 500


@export_bp.route('/bulk', methods=['POST'])
@login_required
@admin_required
@raw_response
def export_bulk_sessions():
    """Export multiple sessions as ZIP of ZIPs"""
    try:
        data = request.get_json()
        session_ids = data.get('session_ids', [])
        
        if not session_ids:
            return jsonify({"error": "No session IDs provided"}), 400
        
        zip_buffer = ExportService.export_bulk_sessions(session_ids)
        filename = ExportService.get_bulk_export_filename()
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        return jsonify({"error": f"Bulk export failed: {str(e)}"}), 500


@export_bp.route('/all-sessions')
@login_required
@admin_required
@raw_response
def export_all_sessions():
    """Export all sessions organized by session number"""
    try:
        zip_buffer = ExportService.export_sessions_by_session_number()
        filename = ExportService.get_all_sessions_export_filename()
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        return jsonify({"error": f"All sessions export failed: {str(e)}"}), 500


@export_bp.route('/session/<session_id>/delete', methods=['DELETE'])
@admin_required
@api_response
def delete_session(session_id):
    """Delete a session with all related data"""
    try:
        result = SessionManager.delete_session(session_id)
        return result, 200
    except ValueError as e:
        return {"success": False, "message": str(e)}, 404
    except Exception as e:
        return {"success": False, "message": f"Failed to delete session: {str(e)}"}, 500


@export_bp.route('/incomplete-sessions')
@login_required
@admin_required
@api_response
def get_incomplete_sessions():
    """Get all incomplete sessions (LLM_IN_PROGRESS, PHQ_IN_PROGRESS, etc.)"""
    try:
        # Get sessions with incomplete status
        incomplete_statuses = ['LLM_IN_PROGRESS', 'PHQ_IN_PROGRESS', 'BOTH_IN_PROGRESS', 'CAMERA_CHECK', 'CONSENT', 'CREATED']
        
        from ...model.assessment.sessions import AssessmentSession
        from ...db import get_session
        
        with get_session() as db:
            sessions = db.query(AssessmentSession).filter(
                AssessmentSession.status.in_(incomplete_statuses)
            ).order_by(AssessmentSession.updated_at.desc()).all()
            
            session_data = []
            for session in sessions:
                session_data.append({
                    "id": session.id,
                    "user_id": session.user_id,
                    "status": session.status,
                    "completion_percentage": session.completion_percentage,
                    "created_at": session.created_at.isoformat(),
                    "updated_at": session.updated_at.isoformat(),
                    "consent_completed": session.consent_completed_at is not None,
                    "camera_completed": session.camera_completed,
                    "phq_completed": session.phq_completed_at is not None,
                    "llm_completed": session.llm_completed_at is not None,
                    "is_first": session.is_first,
                    "session_number": getattr(session, 'session_number', 1),
                    "session_attempt": getattr(session, 'session_attempt', 1),
                    "reset_count": getattr(session, 'reset_count', 0)
                })
        
        return {
            "sessions": session_data,
            "total": len(session_data)
        }, 200
        
    except Exception as e:
        return {"success": False, "message": f"Failed to get incomplete sessions: {str(e)}"}, 500


@export_bp.route('/session/<session_id>/progress')
@login_required
@admin_required
@api_response
def get_session_progress(session_id):
    """Get detailed progress for a specific session"""
    try:
        session = SessionManager.get_session(session_id)
        if not session:
            return {"success": False, "message": "Session not found"}, 404
        
        # Get PHQ progress
        phq_progress = None
        if session.phq_completed_at or session.status in ['PHQ_IN_PROGRESS', 'BOTH_IN_PROGRESS']:
            from ...services.assessment.phqService import PHQResponseService
            try:
                phq_responses = PHQResponseService.get_session_responses(session_id)
                if phq_responses:
                    phq_progress = {
                        "completed": session.phq_completed_at is not None,
                        "response_count": len(phq_responses.responses) if phq_responses.responses else 0,
                        "total_score": PHQResponseService.calculate_session_score(session_id)
                    }
            except Exception:
                phq_progress = {"completed": False, "response_count": 0, "total_score": 0}
        
        # Get LLM progress  
        llm_progress = None
        if session.llm_completed_at or session.status in ['LLM_IN_PROGRESS', 'BOTH_IN_PROGRESS']:
            from ...services.assessment.llmService import LLMConversationService
            try:
                conversations = LLMConversationService.get_session_conversations(session_id)
                llm_progress = {
                    "completed": session.llm_completed_at is not None,
                    "conversation_count": len(conversations) if conversations else 0,
                    "conversation_ended": any(c.get("has_end_conversation", False) for c in conversations) if conversations else False
                }
            except Exception:
                llm_progress = {"completed": False, "conversation_count": 0, "conversation_ended": False}
        
        return {
            "session_id": session_id,
            "status": session.status,
            "completion_percentage": session.completion_percentage,
            "consent_completed": session.consent_completed_at is not None,
            "camera_completed": session.camera_completed,
            "phq_progress": phq_progress,
            "llm_progress": llm_progress,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat()
        }, 200
        
    except Exception as e:
        return {"success": False, "message": f"Failed to get session progress: {str(e)}"}, 500


@export_bp.route('/session/<session_id>/mark-complete', methods=['POST'])
@admin_required
@api_response
def mark_session_complete(session_id):
    """Manually mark a session as complete (admin override)"""
    try:
        session = SessionManager.get_session(session_id)
        if not session:
            return {"success": False, "message": "Session not found"}, 404

        if session.status == 'COMPLETED':
            return {"success": False, "message": "Session is already completed"}, 400

        from ...db import get_session
        with get_session() as db:
            # Mark all assessments as completed if not already
            if not session.phq_completed_at:
                session.phq_completed_at = session.updated_at
            if not session.llm_completed_at:
                session.llm_completed_at = session.updated_at

            # Mark session as completed
            session.complete_session()
            db.commit()

        return {
            "success": True,
            "message": f"Session {session_id} marked as complete",
            "session_id": session_id,
            "new_status": "COMPLETED"
        }, 200

    except Exception as e:
        return {"success": False, "message": f"Failed to mark session complete: {str(e)}"}, 500


# ============= FACIAL ANALYSIS EXPORT ROUTES =============

@export_bp.route('/facial-analysis/session/<session_id>')
@login_required
@admin_required
@raw_response
def export_session_facial_analysis(session_id):
    """Export single session with facial analysis JSONL + processed images"""
    try:
        zip_buffer = ExportService.export_session_with_facial_analysis(session_id)
        filename = ExportService.get_facial_analysis_export_filename(session_id)

        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )

    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Facial analysis export failed: {str(e)}"}), 500


@export_bp.route('/facial-analysis/bulk', methods=['POST'])
@login_required
@admin_required
@raw_response
def export_bulk_facial_analysis():
    """Export multiple sessions with facial analysis as ZIP of ZIPs"""
    try:
        data = request.get_json()
        session_ids = data.get('session_ids', [])

        if not session_ids:
            return jsonify({"error": "No session IDs provided"}), 400

        zip_buffer = ExportService.export_bulk_facial_analysis(session_ids)
        filename = ExportService.get_bulk_facial_analysis_export_filename()

        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )

    except Exception as e:
        return jsonify({"error": f"Bulk facial analysis export failed: {str(e)}"}), 500


@export_bp.route('/facial-analysis/sessions-list')
@login_required
@admin_required
@api_response
def get_facial_analysis_sessions():
    """Get all sessions with completed facial analysis (both PHQ and LLM)"""
    try:
        from ...model.assessment.sessions import AssessmentSession
        from ...model.assessment.facial_analysis import SessionFacialAnalysis
        from ...db import get_session

        with get_session() as db:
            # Get all sessions
            sessions = db.query(AssessmentSession).filter_by(status='COMPLETED').all()

            session_data = []
            for session in sessions:
                # Check facial analysis status
                phq_analysis = db.query(SessionFacialAnalysis).filter_by(
                    session_id=session.id,
                    assessment_type='PHQ'
                ).first()

                llm_analysis = db.query(SessionFacialAnalysis).filter_by(
                    session_id=session.id,
                    assessment_type='LLM'
                ).first()

                phq_status = phq_analysis.status if phq_analysis else 'not_started'
                llm_status = llm_analysis.status if llm_analysis else 'not_started'

                # Check if both are completed
                both_completed = (phq_status == 'completed' and llm_status == 'completed')

                session_data.append({
                    "id": session.id,
                    "user_id": session.user_id,  # CRITICAL: For UI grouping by user
                    "username": session.user.uname if session.user else 'Unknown',
                    "email": session.user.email if session.user else 'Unknown',  # CRITICAL: For UI display in rowspan
                    "session_number": session.session_number,
                    "status": session.status,
                    "created_at": session.created_at.isoformat(),
                    "phq_analysis_status": phq_status,
                    "llm_analysis_status": llm_status,
                    "both_completed": both_completed,
                    "can_download": both_completed
                })

        return {
            "sessions": session_data,
            "total": len(session_data)
        }, 200

    except Exception as e:
        return {"success": False, "message": f"Failed to get facial analysis sessions: {str(e)}"}, 500