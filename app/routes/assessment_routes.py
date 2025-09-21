# app/routes/assessment_routes.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, Response, stream_with_context
from flask_login import current_user, login_required
from ..decorators import raw_response, api_response, user_required
from ..services.session.sessionManager import SessionManager
from ..services.admin.phqService import PHQService
from ..services.admin.llmService import LLMService
from ..services.llm.chatService import LLMChatService
import time
import hashlib
import hmac

assessment_bp = Blueprint('assessment', __name__, url_prefix='/assessment')
def _save_camera_capture_sync(session_id, file_data, capture_trigger, assessment_id, capture_type, camera_settings_snapshot):
    """Async wrapper for camera capture saving - runs in thread pool"""
    from ..services.camera.cameraCaptureService import CameraCaptureService
    return CameraCaptureService.save_capture(
        session_id=session_id,
        file_data=file_data,
        capture_trigger=capture_trigger,
        assessment_id=assessment_id,
        capture_type=capture_type,
        camera_settings_snapshot=camera_settings_snapshot
    )


@assessment_bp.route('/start', methods=['POST'])
@login_required
def start_assessment():
    """Start assessment - auto-reset incomplete sessions or create new one"""
    try:
        # Clear any existing refresh flags for this user
        # This prevents old session flags from interfering with new sessions
        # We'll handle this in the template with JavaScript
        # Check for recoverable sessions first
        recoverable_session = SessionManager.get_user_recoverable_session(current_user.id)
        
        if recoverable_session:
            # User has incomplete session - auto-reset it (same as "Coba Lagi" button)
            result = SessionManager.reset_session_to_new_attempt(
                recoverable_session.id, 
                "AUTO_RESET_ON_START"
            )
            flash('Session sebelumnya direset. Memulai assessment baru.', 'success')
            return redirect(url_for('assessment.assessment_dashboard'))

        # No incomplete session - create new session
        if not SessionManager.can_create_new_session(current_user.id):
            flash('Anda sudah mencapai maksimum 2 sesi assessment.', 'error')
            return redirect(url_for('main.serve_index'))

        # Create new session with improved system
        session = SessionManager.create_session(current_user.id)
        print(f"Created new session {session.id}")
        
        flash('Assessment baru berhasil dibuat!', 'success')
        return redirect(url_for('assessment.assessment_dashboard'))

    except ValueError as e:
        error_message = str(e)
        if "Pengaturan assessment belum lengkap" in error_message:
            flash('Pengaturan assessment belum dikonfigurasi. Silakan menghubungi penyelenggara.', 'error')
            return redirect(url_for('main.settings_not_configured'))
        else:
            flash(error_message, 'error')
            return redirect(url_for('main.serve_index'))
    except Exception as e:
        print(f"Error creating session: {str(e)}")
        flash(str(e), 'error')
        return redirect(url_for('main.serve_index'))


@assessment_bp.route('/')
@login_required
@raw_response
def assessment_dashboard():
    """Assessment dashboard with improved session handling"""
    # Check if settings are configured
    settings_check = SessionManager.check_assessment_settings_configured()
    if not settings_check['all_configured']:
        return redirect(url_for('main.settings_not_configured'))
    active_session = SessionManager.get_active_session(current_user.id)
    if not active_session:
        return redirect(url_for('main.serve_index'))
    session = active_session
    reset_session_id = request.args.get('reset_session')
    if reset_session_id and reset_session_id == str(session.id):
        try:
            result = SessionManager.reset_session_to_new_attempt(session.id, "PAGE_REFRESH")
            flash("Session berhasil direset. Anda dapat memulai assessment baru.", "success")
            return redirect(url_for('assessment.assessment_dashboard'))
        except Exception as e:
            flash(f"Gagal mereset session: {str(e)}", "error")
            return redirect(url_for('assessment.assessment_dashboard'))
    if not session.consent_completed_at:
        print(" No consent - redirecting to consent")
        return redirect(url_for('assessment.consent_page'))
    if session.status == 'CONSENT' and not session.camera_completed:
        print(" No camera check - redirecting to camera")
        return redirect(url_for('assessment.camera_check'))
    
    # Handle CAMERA_CHECK status properly
    if session.status == 'CAMERA_CHECK' and not session.camera_completed:
        return redirect(url_for('assessment.camera_check'))
    # Direct redirect logic for assessments - automatic flow
    if session.status in ['PHQ_IN_PROGRESS', 'LLM_IN_PROGRESS', 'BOTH_IN_PROGRESS']:
        next_assessment = session.next_assessment_type
        if next_assessment == 'phq':
            return redirect(url_for('assessment.phq_assessment'))
        elif next_assessment == 'llm':
            return redirect(url_for('assessment.llm_assessment'))

    # If camera check is done but no assessment started, start first assessment
    if session.status == 'CAMERA_CHECK' and session.camera_completed:
        if session.is_first == 'phq':
            return redirect(url_for('assessment.phq_assessment'))
        else:
            return redirect(url_for('assessment.llm_assessment'))
    if session.status != 'COMPLETED':
        print(f" Unexpected dashboard state - status: {session.status}")

    return render_template('assessment/dashboard.html',
                           user=current_user,
                           session=session)


@assessment_bp.route('/consent')
@login_required
@raw_response
def consent_page():
    """Show consent form"""
    active_session = SessionManager.get_active_session(current_user.id)

    if not active_session:
        return redirect(url_for('main.serve_index'))

    # Get consent settings from database
    from ..services.admin.consentService import ConsentService
    db_settings = ConsentService.get_settings()
    
    if db_settings:
        # Get first active setting
        consent_setting = db_settings[0]
        consent_data = {
            'title': consent_setting.get('title', ''),
            'content': consent_setting.get('content', ''),
            'footer_text': consent_setting.get('footer_text', '')
        }
    else:
        # Fallback to default settings
        default_settings = ConsentService.get_default_settings()
        consent_data = {
            'title': default_settings.get('title', ''),
            'content': default_settings.get('content', ''),
            'footer_text': default_settings.get('footer_text', '')
        }

    return render_template('assessment/consent.html',
                           user=current_user,
                           session=active_session,
                           consent_data=consent_data)


@assessment_bp.route('/consent', methods=['POST'])
@login_required
@raw_response
def submit_consent():
    """Submit consent and proceed to camera check"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        consent_agreed = data.get('consent_agreed', False)

        if not consent_agreed:
            return jsonify({"status": "SNAFU", "error": "Persetujuan diperlukan"}), 400

        # Update session with consent
        consent_data = {
            "consent_agreed": True,
            "consent_timestamp": data.get('timestamp')
        }

        SessionManager.update_consent_data(session_id, consent_data)

        return jsonify({"status": "OLKORECT", "next_step": "camera_check"})

    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@assessment_bp.route('/camera-check')
@login_required
@raw_response
def camera_check():
    """Camera permission and functionality check"""
    active_session = SessionManager.get_active_session(current_user.id)

    if not active_session or not active_session.consent_completed_at:
        return redirect(url_for('assessment.consent_page'))
    # problem 2 
    return render_template('assessment/camera_check.html',
                           user=current_user,
                           session=active_session)


@assessment_bp.route('/camera-check', methods=['POST'])
@login_required
@raw_response
def submit_camera_check():
    """Submit camera check and proceed to assessment"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        camera_working = data.get('camera_working', False)

        if not camera_working:
            return jsonify({"status": "SNAFU", "error": "Kamera harus berfungsi untuk melanjutkan"}), 400

        # Update session with camera completion
        SessionManager.complete_camera_check(session_id)

        return jsonify({"status": "OLKORECT", "next_step": "assessment"})

    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500
@assessment_bp.route('/phq')
@login_required
@raw_response
def phq_assessment():
    """PHQ Assessment Page"""
    settings_check = SessionManager.check_assessment_settings_configured()
    if not settings_check['all_configured']:
        return redirect(url_for('main.settings_not_configured'))
    active_session = SessionManager.get_active_session(current_user.id)

    if not active_session:
        return redirect(url_for('main.serve_index'))

    session = active_session

    # Load camera settings for frontend
    from ..services.camera.cameraCaptureService import CameraCaptureService
    camera_settings = CameraCaptureService.get_camera_settings_for_session(session.id)
    camera_settings_dict = CameraCaptureService.create_settings_snapshot(camera_settings) if camera_settings else {}

    # Check prerequisites for assessment
    if not session.consent_completed_at:
        return redirect(url_for('assessment.consent_page'))

    # If session is already in PHQ_IN_PROGRESS or LLM_IN_PROGRESS, camera check is implied to be done
    if session.status in ['CREATED', 'CONSENT', 'CAMERA_CHECK'] and not session.camera_completed:
        return redirect(url_for('assessment.camera_check'))

    # If camera check just completed, transition session status to proper assessment status
    if session.status == 'CAMERA_CHECK' and session.camera_completed:
        if session.is_first == 'phq':
            SessionManager.complete_camera_check(session.id)
            session = SessionManager.get_session(session.id)
        else:
            # PHQ is not first, redirect to LLM
            return redirect(url_for('assessment.llm_assessment'))
    
    # Check if PHQ assessment is already completed
    if session.phq_completed_at:
        flash('PHQ assessment sudah selesai. Tidak bisa mengulang.', 'info')
        return redirect(url_for('assessment.assessment_dashboard'))
    
    next_assessment = session.next_assessment_type
    if next_assessment != 'phq':
        if next_assessment == 'llm':
            return redirect(url_for('assessment.llm_assessment'))
        elif session.status == 'COMPLETED':
            return redirect(url_for('assessment.assessment_dashboard'))
        else:
            return redirect(url_for('assessment.assessment_dashboard'))
    
    # AUTO-REDIRECT: If this is a fresh PHQ start, show instructions first
    return redirect(url_for('phq_assessment.phq_instructions'))


@assessment_bp.route('/phq/start')
@login_required  
@raw_response
def phq_assessment_start():
    """Actual PHQ Assessment Page - comes AFTER instructions"""
    settings_check = SessionManager.check_assessment_settings_configured()
    if not settings_check['all_configured']:
        return redirect(url_for('main.settings_not_configured'))
    active_session = SessionManager.get_active_session(current_user.id)

    if not active_session:
        return redirect(url_for('main.serve_index'))

    session = active_session

    # Load camera settings for frontend
    from ..services.camera.cameraCaptureService import CameraCaptureService
    camera_settings = CameraCaptureService.get_camera_settings_for_session(session.id)
    camera_settings_dict = CameraCaptureService.create_settings_snapshot(camera_settings) if camera_settings else {}

    # Check prerequisites for assessment
    if not session.consent_completed_at:
        return redirect(url_for('assessment.consent_page'))

    # If session is already in PHQ_IN_PROGRESS or LLM_IN_PROGRESS, camera check is implied to be done
    if session.status in ['CREATED', 'CONSENT', 'CAMERA_CHECK'] and not session.camera_completed:
        return redirect(url_for('assessment.camera_check'))

    # If camera check just completed, transition session status to proper assessment status
    if session.status == 'CAMERA_CHECK' and session.camera_completed:
        if session.is_first == 'phq':
            SessionManager.complete_camera_check(session.id)
            session = SessionManager.get_session(session.id)
        else:
            # PHQ is not first, redirect to LLM
            return redirect(url_for('assessment.llm_assessment'))
    
    # Check if PHQ assessment is already completed
    if session.phq_completed_at:
        flash('PHQ assessment sudah selesai. Tidak bisa mengulang.', 'info')
        return redirect(url_for('assessment.assessment_dashboard'))
    
    next_assessment = session.next_assessment_type
    if next_assessment != 'phq':
        if next_assessment == 'llm':
            return redirect(url_for('assessment.llm_assessment'))
        elif session.status == 'COMPLETED':
            return redirect(url_for('assessment.assessment_dashboard'))
        else:
            return redirect(url_for('assessment.assessment_dashboard'))
        # problem 3. 
    return render_template('assessment/phq.html',
                           user=current_user,
                           session=session,
                           camera_settings=camera_settings_dict)


@assessment_bp.route('/llm')
@login_required
@raw_response
def llm_assessment():
    """LLM Chat Assessment Page"""

    # Check if settings are configured
    settings_check = SessionManager.check_assessment_settings_configured()
    if not settings_check['all_configured']:
        return redirect(url_for('main.settings_not_configured'))

    active_session = SessionManager.get_active_session(current_user.id)

    if not active_session:
        return redirect(url_for('main.serve_index'))

    session = active_session

    # Check prerequisites for assessment
    if not session.consent_completed_at:
        return redirect(url_for('assessment.consent_page'))

    # If session is already in PHQ_IN_PROGRESS or LLM_IN_PROGRESS, camera check is implied to be done
    if session.status in ['CREATED', 'CONSENT', 'CAMERA_CHECK'] and not session.camera_completed:
        return redirect(url_for('assessment.camera_check'))

    # If camera check just completed, transition session status to proper assessment status
    if session.status == 'CAMERA_CHECK' and session.camera_completed:
        if session.is_first == 'llm':
            SessionManager.complete_camera_check(session.id)
            # Refresh session after status change
            session = SessionManager.get_session(session.id)
        else:
            # LLM is not first, redirect to PHQ
            return redirect(url_for('assessment.phq_assessment'))

    # Check if LLM assessment is already completed
    if session.llm_completed_at:
        flash('LLM assessment sudah selesai. Tidak bisa mengulang.', 'info')
        return redirect(url_for('assessment.assessment_dashboard'))

    # Check session should do LLM now based on status and completion
    next_assessment = session.next_assessment_type
    if next_assessment != 'llm':
        if next_assessment == 'phq':
            return redirect(url_for('assessment.phq_assessment'))
        elif session.status == 'COMPLETED':
            return redirect(url_for('assessment.assessment_dashboard'))
        else:
            return redirect(url_for('assessment.assessment_dashboard'))
    # AUTO-REDIRECT: If this is a fresh LLM start, show instructions first
    return redirect(url_for('llm_assessment.llm_instructions'))


@assessment_bp.route('/llm/start')
@login_required
@raw_response  
def llm_assessment_start():
    """Actual LLM Chat Assessment Page - comes AFTER instructions"""

    # Check if settings are configured
    settings_check = SessionManager.check_assessment_settings_configured()
    if not settings_check['all_configured']:
        return redirect(url_for('main.settings_not_configured'))

    active_session = SessionManager.get_active_session(current_user.id)

    if not active_session:
        return redirect(url_for('main.serve_index'))

    session = active_session

    # Check prerequisites for assessment
    if not session.consent_completed_at:
        return redirect(url_for('assessment.consent_page'))

    # If session is already in PHQ_IN_PROGRESS or LLM_IN_PROGRESS, camera check is implied to be done
    if session.status in ['CREATED', 'CONSENT', 'CAMERA_CHECK'] and not session.camera_completed:
        return redirect(url_for('assessment.camera_check'))

    # If camera check just completed, transition session status to proper assessment status
    if session.status == 'CAMERA_CHECK' and session.camera_completed:
        if session.is_first == 'llm':
            SessionManager.complete_camera_check(session.id)
            # Refresh session after status change
            session = SessionManager.get_session(session.id)
        else:
            # LLM is not first, redirect to PHQ
            return redirect(url_for('assessment.phq_assessment'))

    # Check if LLM assessment is already completed
    if session.llm_completed_at:
        flash('LLM assessment sudah selesai. Tidak bisa mengulang.', 'info')
        return redirect(url_for('assessment.assessment_dashboard'))

    # Check session should do LLM now based on status and completion
    next_assessment = session.next_assessment_type
    if next_assessment != 'llm':
        if next_assessment == 'phq':
            return redirect(url_for('assessment.phq_assessment'))
        elif session.status == 'COMPLETED':
            return redirect(url_for('assessment.assessment_dashboard'))
        else:
            return redirect(url_for('assessment.assessment_dashboard'))
    from ..services.camera.cameraCaptureService import CameraCaptureService
    camera_settings = CameraCaptureService.get_camera_settings_for_session(session.id)
    camera_settings_dict = CameraCaptureService.create_settings_snapshot(camera_settings) if camera_settings else {}
    return render_template('assessment/llm.html',
                           user=current_user,
                           session=session,
                           camera_settings=camera_settings_dict)


@assessment_bp.route('/complete/<assessment_type>/<session_id>', methods=['POST'])
@login_required
@raw_response
def complete_assessment(assessment_type, session_id):
    """Universal completion handler for any assessment type"""
    session = SessionManager.get_session(session_id)

    # Complete the specified assessment
    if assessment_type == 'phq':
        SessionManager.complete_phq_assessment(session.id)
    elif assessment_type == 'llm':
        SessionManager.complete_llm_assessment(session.id)
    else:
        return jsonify({"status": "SNAFU", "error": "Invalid assessment type"}), 400

    # Get updated session and flow plan
    updated_session = SessionManager.get_session(session.id)
    flow_plan = updated_session.assessment_order.get('flow_plan', {}) if updated_session.assessment_order else {}

    # Determine next redirect based on pre-planned flow
    next_redirect_key = f'{assessment_type}_complete_redirect'
    next_redirect = flow_plan.get(next_redirect_key)
    
    # If no flow plan, determine next step based on session status
    if not next_redirect:
        if updated_session.status == 'PHQ_IN_PROGRESS':
            next_redirect = '/assessment/phq'
        elif updated_session.status == 'LLM_IN_PROGRESS':  
            next_redirect = '/assessment/llm'
        else:
            next_redirect = '/assessment/'

    # Check if both assessments are complete
    if updated_session.status == 'COMPLETED':
        next_redirect = flow_plan.get('both_complete_redirect', '/assessment/')
        completion_message = "Semua assessment selesai! 🎉"
    else:
        next_assessment = 'LLM' if assessment_type == 'phq' else 'PHQ'
        completion_message = f"{assessment_type.upper()} selesai! Lanjut ke {next_assessment}..."

    return jsonify({
        "status": "OLKORECT",
        "data": {
            "assessment_completed": assessment_type,
            "session_status": updated_session.status,
            "next_redirect": next_redirect
        },
        "message": completion_message
    })


@assessment_bp.route('/reset-session/<session_id>', methods=['POST'])
@login_required
def reset_session_to_new_attempt(session_id):
    """Reset session and auto-create new session (improved UX)"""
    try:
        session = SessionManager.get_session(session_id)
        if not session:
            flash('Session tidak ditemukan.', 'error')
            return redirect(url_for('main.serve_index'))
        
        # Verify session belongs to current user
        if int(session.user_id) != int(current_user.id):
            flash('Akses ditolak.', 'error')
            return redirect(url_for('main.serve_index'))
        
        reason = request.form.get('reason', 'USER_INITIATED_RESET')
        
        # Delete old session and create new one (with camera cleanup)
        delete_result, new_session = SessionManager.delete_and_create_new_session(
            session.id, current_user.id, reason
        )
        
        flash('Session direset dan session baru telah dibuat. Memulai assessment baru.', 'success')
        return redirect(url_for('assessment.assessment_dashboard'))
        
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('main.serve_index'))
    except Exception as e:
        print(f" Error resetting session: {str(e)}")
        flash(str(e), 'error')
        return redirect(url_for('main.serve_index'))



@assessment_bp.route('/sessions', methods=['GET'])
@login_required
@raw_response
def get_user_sessions():
    """Get all sessions for current user with status indicators"""
    try:
        sessions_with_status = SessionManager.get_user_sessions_with_status(current_user.id)

        # Convert datetime objects to ISO format for JSON serialization
        for session in sessions_with_status:
            if session['created_at']:
                session['created_at'] = session['created_at'].isoformat()
            if session['completed_at']:
                session['completed_at'] = session['completed_at'].isoformat()

        return jsonify(sessions_with_status)

    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@assessment_bp.route('/recover-check', methods=['GET'])
@login_required
@raw_response
def check_recoverable_session():
    """Check if user has a recoverable session"""
    try:
        from ..services.session.sessionManager import SessionManager

        recoverable_session = SessionManager.get_user_recoverable_session(current_user.id)

        if recoverable_session:
            return jsonify({
                "status": "OLKORECT",
                "has_recoverable": True,
                "session": {
                    "id": recoverable_session.id,
                    "status": recoverable_session.status,
                    "completion_percentage": recoverable_session.completion_percentage,
                    "created_at": recoverable_session.created_at.isoformat(),
                    "failure_reason": recoverable_session.failure_reason,
                    "phq_completed": recoverable_session.phq_completed_at is not None,
                    "llm_completed": recoverable_session.llm_completed_at is not None,
                    "consent_completed": recoverable_session.consent_completed_at is not None
                }
            })
        else:
            return jsonify({
                "status": "OLKORECT",
                "has_recoverable": False
            })

    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500




@assessment_bp.route('/abandon/<session_id>', methods=['POST'])
@login_required
def abandon_session(session_id):
    """Mark session as abandoned (user quit)"""
    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'User abandoned session')

        from ..services.session.sessionManager import SessionManager

        # Verify session belongs to current user
        session = SessionManager.get_session(session_id)
        if not session or int(session.user_id) != int(current_user.id):
            return jsonify({"status": "SNAFU", "error": "Session not found or access denied"}), 403

        # Abandon the session
        abandoned_session = SessionManager.abandon_session(session_id, reason)

        return jsonify({
            "status": "OLKORECT",
            "message": "Session ditandai sebagai abandoned",
            "session_id": abandoned_session.id,
            "session_status": abandoned_session.status
        })

    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


# Camera Capture Endpoints
@assessment_bp.route('/camera/upload', methods=['POST'])
@login_required
@raw_response
async def upload_camera_captures():
    """Upload camera captures via AJAX"""
    try:
        from ..services.camera.cameraCaptureService import CameraCaptureService
        
        # Get form data
        session_id = request.form.get('session_id')
        if not session_id:
            return jsonify({"status": "SNAFU", "error": "session_id required"}), 400

        # Verify session belongs to current user
        session = SessionManager.get_session(session_id)
        if not session or int(session.user_id) != int(current_user.id):
            return jsonify({"status": "SNAFU", "error": "Session not found or access denied"}), 403

        # Get camera settings for this session
        camera_settings = CameraCaptureService.get_camera_settings_for_session(session_id)
        settings_snapshot = CameraCaptureService.create_settings_snapshot(camera_settings)

        captures_saved = []
        
        # Process each uploaded file
        for key in request.files:
            if key.startswith('capture_'):
                file = request.files[key]
                if file and file.filename:
                    # Extract metadata from form
                    metadata_key = key.replace('capture_', 'metadata_')
                    metadata_json = request.form.get(metadata_key, '{}')
                    
                    try:
                        import json
                        metadata = json.loads(metadata_json)
                    except:
                        metadata = {}
                    
                    # Get capture details
                    trigger = metadata.get('trigger', 'MANUAL')
                    phq_response_id = metadata.get('phq_response_id')
                    llm_conversation_id = metadata.get('llm_conversation_id')
                    
                    # Interval captures are stored with session_id only
                    # They will be bulk-linked when assessments complete
                    
                    # Check if we should capture based on settings
                    if camera_settings and not CameraCaptureService.should_capture_on_trigger(camera_settings, trigger):
                        continue  # Skip this capture
                    
                    # Save capture (async to prevent blocking other users)
                    file_data = file.read()
                    capture = await _save_camera_capture_sync(
                        session_id=session_id,
                        file_data=file_data,
                        capture_trigger=trigger,
                        assessment_id=phq_response_id or llm_conversation_id,
                        capture_type='PHQ' if phq_response_id else 'LLM' if llm_conversation_id else 'GENERAL',
                        camera_settings_snapshot=settings_snapshot
                    )
                    
                    captures_saved.append({
                        'id': capture.id,
                        'filename': capture.filename,
                        'trigger': capture.capture_trigger,
                        'timestamp': capture.timestamp.isoformat()
                    })

        return jsonify({
            "status": "OLKORECT", 
            "message": f"Uploaded {len(captures_saved)} captures",
            "captures": captures_saved
        })

    except Exception as e:
        print(f"Error uploading captures: {str(e)}")
        return jsonify({"status": "SNAFU", "error": str(e)}), 500



@assessment_bp.route('/camera/session/<session_id>')
@login_required
@raw_response
def get_session_camera_captures(session_id):
    """Get all camera captures for a session"""
    try:
        from ..services.camera.cameraCaptureService import CameraCaptureService
        
        # Verify session belongs to current user
        session = SessionManager.get_session(session_id)
        if not session or int(session.user_id) != int(current_user.id):
            return jsonify({"status": "SNAFU", "error": "Session not found or access denied"}), 403

        captures = CameraCaptureService.get_session_captures(session_id)
        
        return jsonify({
            "status": "OLKORECT",
            "session_id": session_id,
            "captures": captures,
            "total_captures": len(captures)
        })

    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@assessment_bp.route("/restart-phq/<session_id>", methods=["POST"])
@login_required
def restart_phq_assessment(session_id):
    """Restart PHQ assessment by creating new session (improved UX)"""
    try:
        # Validate session belongs to current user
        session = SessionManager.get_session(session_id)
        if not session or int(session.user_id) != int(current_user.id):
            flash("Session tidak ditemukan atau akses ditolak.", "error")
            return redirect(url_for("assessment.assessment_dashboard"))

        # Delete old session and create new one (with camera cleanup)
        delete_result, new_session = SessionManager.delete_and_create_new_session(
            session_id, current_user.id, "PHQ_RESTART"
        )
        
        flash("PHQ assessment direset. Session baru telah dibuat.", "success")
        return redirect(url_for("assessment.assessment_dashboard"))
        
    except Exception as e:
        flash(f"Gagal mereset PHQ assessment: {str(e)}", "error")
        return redirect(url_for("assessment.assessment_dashboard"))


@assessment_bp.route("/restart-llm/<session_id>", methods=["POST"])
@login_required
def restart_llm_assessment(session_id):
    """Restart LLM assessment by creating new session (improved UX)"""
    try:
        # Validate session belongs to current user
        session = SessionManager.get_session(session_id)
        if not session or int(session.user_id) != int(current_user.id):
            flash("Session tidak ditemukan atau akses ditolak.", "error")
            return redirect(url_for("assessment.assessment_dashboard"))

        # Clear LangChain memory first (before deleting session)
        from ..services.llm.chatService import get_by_session_id, store
        try:
            history = get_by_session_id(str(session_id))
            history.clear()
            if str(session_id) in store:
                del store[str(session_id)]
        except Exception:
            pass  # Ignore if memory doesn't exist
        
        # Delete old session and create new one (with camera cleanup)
        delete_result, new_session = SessionManager.delete_and_create_new_session(
            session_id, current_user.id, "LLM_RESTART"
        )
        
        flash("LLM assessment direset. Session baru telah dibuat.", "success")
        return redirect(url_for("assessment.assessment_dashboard"))
        
    except Exception as e:
        flash(f"Gagal mereset LLM assessment: {str(e)}", "error")
        return redirect(url_for("assessment.assessment_dashboard"))


@assessment_bp.route("/reset-session-on-refresh/<session_id>", methods=["POST"])
@login_required
def reset_session_on_refresh(session_id):
    """Reset session when user refreshes the page (improved UX)"""
    try:
        # Validate session belongs to current user
        session = SessionManager.get_session(session_id)
        if not session or int(session.user_id) != int(current_user.id):
            flash("Session tidak ditemukan atau akses ditolak.", "error")
            return redirect(url_for("main.serve_index"))

        # Delete old session and create new one (with camera cleanup)
        delete_result, new_session = SessionManager.delete_and_create_new_session(
            session_id, current_user.id, "PAGE_REFRESH"
        )
        
        flash("Session berhasil direset. Session baru telah dibuat.", "success")
        return redirect(url_for("assessment.assessment_dashboard"))
        
    except Exception as e:
        flash(f"Gagal mereset session: {str(e)}", "error")
        return redirect(url_for("assessment.assessment_dashboard"))


@assessment_bp.route('/thank-you')
@login_required
@raw_response
def thank_you():
    """Thank you page after assessment completion - no validation needed"""
    # Get user's most recent session for the summary
    user_sessions = SessionManager.get_user_sessions_with_status(current_user.id)
    last_session = user_sessions[0] if user_sessions else None
    
    # Invalidate the current session in background (token cleanup)
    # from flask_login import logout_user
    # logout_user()
    
    # Show thank you page with last completed session info
    return render_template('assessment/thank_you.html', 
                         user=current_user,
                         session=last_session)

