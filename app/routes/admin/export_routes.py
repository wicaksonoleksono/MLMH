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