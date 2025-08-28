# app/routes/assessment_routes.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import current_user, login_required
from ..decorators import raw_response
from ..services.sessionService import SessionService
from ..services.admin.consentService import ConsentService
from ..db import get_session

assessment_bp = Blueprint('assessment', __name__, url_prefix='/assessment')


@assessment_bp.route('/start', methods=['POST'])
@login_required
@raw_response
def start_assessment():
    """Create new assessment session with recovery options"""
    try:

        # Check if user can create new session
        if not SessionService.can_create_session(current_user.id):
            return jsonify({
                "status": "SNAFU",
                "error": f"Maksimal {SessionService.MAX_SESSIONS_PER_USER} sesi aktif per pengguna"
            }), 400

        # Create new session with improved system
        session = SessionService.create_session(current_user.id)

        return jsonify({
            "status": "OLKORECT",
            "session_id": session.id,
            "session_token": session.session_token,
            "is_first": session.is_first,
            "assessment_order": session.assessment_order,
            "next_step": "consent"
        })

    except ValueError as e:
        error_message = str(e)
        if "Pengaturan assessment belum lengkap" in error_message:
            return jsonify({
                "status": "SETTINGS_NOT_CONFIGURED",
                "error": "Pengaturan assessment belum dikonfigurasi. Silakan menghubungi penyelenggara.",
                "redirect_url": url_for('main.settings_not_configured')
            }), 400
        else:
            return jsonify({"status": "SNAFU", "error": error_message}), 400
    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@assessment_bp.route('/')
@login_required
@raw_response
def assessment_dashboard():
    """Assessment dashboard with improved session handling"""
    # Check if settings are configured
    settings_check = SessionService.check_assessment_settings_configured()
    if not settings_check['all_configured']:
        return redirect(url_for('main.settings_not_configured'))

    # Check for active session
    active_session = SessionService.get_active_session(current_user.id)

    if not active_session:
        return redirect(url_for('main.serve_index'))

    session = active_session

    # Direct redirect logic based on session flow
    if not session.consent_completed_at:
        return redirect(url_for('assessment.consent_page'))

    if session.status == 'CONSENT' and not session.camera_completed:
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

    return render_template('assessment/dashboard.html',
                           user=current_user,
                           session=session)


@assessment_bp.route('/consent')
@login_required
@raw_response
def consent_page():
    """Show consent form"""
    active_session = SessionService.get_active_session(current_user.id)

    if not active_session:
        return redirect(url_for('main.serve_index'))

    return render_template('assessment/consent.html',
                           user=current_user,
                           session=active_session)


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

        SessionService.update_consent_data(session_id, consent_data)

        return jsonify({"status": "OLKORECT", "next_step": "camera_check"})

    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@assessment_bp.route('/camera-check')
@login_required
@raw_response
def camera_check():
    """Camera permission and functionality check"""
    active_session = SessionService.get_active_session(current_user.id)

    if not active_session or not active_session.consent_completed_at:
        return redirect(url_for('assessment.consent_page'))

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
        SessionService.complete_camera_check(session_id)

        return jsonify({"status": "OLKORECT", "next_step": "assessment"})

    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@assessment_bp.route('/phq')
@login_required
@raw_response
def phq_assessment():
    """PHQ Assessment Page"""
    print(f"DEBUG PHQ: User {current_user.id} accessing PHQ page")

    # Check if settings are configured
    settings_check = SessionService.check_assessment_settings_configured()
    if not settings_check['all_configured']:
        print("DEBUG PHQ: Settings not configured, redirecting")
        return redirect(url_for('main.settings_not_configured'))

    active_session = SessionService.get_active_session(current_user.id)
    print(f"DEBUG PHQ: Active session: {active_session}")

    if not active_session:
        print("DEBUG PHQ: No active session, redirecting to index")
        return redirect(url_for('main.serve_index'))

    session = active_session
    print(f"DEBUG PHQ: Session status: {session.status}")
    print(f"DEBUG PHQ: Session consent: {session.consent_completed_at}")
    print(f"DEBUG PHQ: Session camera: {session.camera_completed}")
    print(f"DEBUG PHQ: Session is_first: {session.is_first}")
    print(f"DEBUG PHQ: Session next_assessment_type: {session.next_assessment_type}")

    # Check prerequisites for assessment
    if not session.consent_completed_at:
        print("DEBUG PHQ: No consent, redirecting to consent")
        return redirect(url_for('assessment.consent_page'))

    # If session is already in PHQ_IN_PROGRESS or LLM_IN_PROGRESS, camera check is implied to be done
    if session.status in ['CREATED', 'CONSENT', 'CAMERA_CHECK'] and not session.camera_completed:
        print("DEBUG PHQ: No camera check, redirecting to camera check")
        return redirect(url_for('assessment.camera_check'))

    # If camera check just completed, transition session status to proper assessment status
    if session.status == 'CAMERA_CHECK' and session.camera_completed:
        print("DEBUG PHQ: Camera check complete, transitioning status")
        if session.is_first == 'phq':
            SessionService.complete_camera_check(session.id)
            # Refresh session after status change
            session = SessionService.get_session(session.id)
            print(f"DEBUG PHQ: Session status after camera check: {session.status}")
        else:
            # PHQ is not first, redirect to LLM
            print("DEBUG PHQ: PHQ not first, redirecting to LLM")
            return redirect(url_for('assessment.llm_assessment'))

    # Check session should do PHQ now based on status and completion
    next_assessment = session.next_assessment_type
    print(f"DEBUG PHQ: Next assessment should be: {next_assessment}")
    if next_assessment != 'phq':
        if next_assessment == 'llm':
            print("DEBUG PHQ: Should do LLM instead, redirecting")
            return redirect(url_for('assessment.llm_assessment'))
        elif session.status == 'COMPLETED':
            print("DEBUG PHQ: Session completed, redirecting to dashboard")
            return redirect(url_for('assessment.assessment_dashboard'))
        else:
            # Unknown state, go to dashboard
            print(f"DEBUG PHQ: Unknown state {session.status}, redirecting to dashboard")
            return redirect(url_for('assessment.assessment_dashboard'))

    print("DEBUG PHQ: All checks passed, rendering PHQ template")
    return render_template('assessment/phq.html',
                           user=current_user,
                           session=session)


@assessment_bp.route('/llm')
@login_required
@raw_response
def llm_assessment():
    """LLM Chat Assessment Page"""
    print(f"DEBUG LLM: User {current_user.id} accessing LLM page")

    # Check if settings are configured
    settings_check = SessionService.check_assessment_settings_configured()
    if not settings_check['all_configured']:
        print("DEBUG LLM: Settings not configured, redirecting")
        return redirect(url_for('main.settings_not_configured'))

    active_session = SessionService.get_active_session(current_user.id)
    print(f"DEBUG LLM: Active session: {active_session}")

    if not active_session:
        print("DEBUG LLM: No active session, redirecting to index")
        return redirect(url_for('main.serve_index'))

    session = active_session
    print(f"DEBUG LLM: Session status: {session.status}")
    print(f"DEBUG LLM: Session consent: {session.consent_completed_at}")
    print(f"DEBUG LLM: Session camera: {session.camera_completed}")
    print(f"DEBUG LLM: Session is_first: {session.is_first}")
    print(f"DEBUG LLM: Session next_assessment_type: {session.next_assessment_type}")

    # Check prerequisites for assessment
    if not session.consent_completed_at:
        print("DEBUG LLM: No consent, redirecting to consent")
        return redirect(url_for('assessment.consent_page'))

    # If session is already in PHQ_IN_PROGRESS or LLM_IN_PROGRESS, camera check is implied to be done
    if session.status in ['CREATED', 'CONSENT', 'CAMERA_CHECK'] and not session.camera_completed:
        print("DEBUG LLM: No camera check, redirecting to camera check")
        return redirect(url_for('assessment.camera_check'))

    # If camera check just completed, transition session status to proper assessment status
    if session.status == 'CAMERA_CHECK' and session.camera_completed:
        print("DEBUG LLM: Camera check complete, transitioning status")
        if session.is_first == 'llm':
            SessionService.complete_camera_check(session.id)
            # Refresh session after status change
            session = SessionService.get_session(session.id)
            print(f"DEBUG LLM: Session status after camera check: {session.status}")
        else:
            # LLM is not first, redirect to PHQ
            print("DEBUG LLM: LLM not first, redirecting to PHQ")
            return redirect(url_for('assessment.phq_assessment'))

    # Check session should do LLM now based on status and completion
    next_assessment = session.next_assessment_type
    print(f"DEBUG LLM: Next assessment should be: {next_assessment}")
    if next_assessment != 'llm':
        if next_assessment == 'phq':
            print("DEBUG LLM: Should do PHQ instead, redirecting")
            return redirect(url_for('assessment.phq_assessment'))
        elif session.status == 'COMPLETED':
            print("DEBUG LLM: Session completed, redirecting to dashboard")
            return redirect(url_for('assessment.assessment_dashboard'))
        else:
            # Unknown state, go to dashboard
            print(f"DEBUG LLM: Unknown state {session.status}, redirecting to dashboard")
            return redirect(url_for('assessment.assessment_dashboard'))

    print("DEBUG LLM: All checks passed, rendering LLM template")
    return render_template('assessment/llm.html',
                           user=current_user,
                           session=session)


@assessment_bp.route('/complete/<assessment_type>/<int:session_id>', methods=['POST'])
@login_required
@raw_response
def complete_assessment(assessment_type, session_id):
    """Universal completion handler for any assessment type"""
    try:
        # Validate session belongs to current user
        session = SessionService.get_session(session_id)
        if not session or session.user_id != current_user.id:
            return jsonify({"status": "SNAFU", "error": "Session not found or access denied"}), 403

        # Complete the specified assessment
        if assessment_type == 'phq':
            SessionService.complete_phq_assessment(session_id)
        elif assessment_type == 'llm':
            SessionService.complete_llm_assessment(session_id)
        else:
            return jsonify({"status": "SNAFU", "error": "Invalid assessment type"}), 400

        # Get updated session and flow plan
        updated_session = SessionService.get_session(session_id)
        flow_plan = updated_session.assessment_order.get('flow_plan', {}) if updated_session.assessment_order else {}

        # Determine next redirect based on pre-planned flow
        next_redirect_key = f'{assessment_type}_complete_redirect'
        next_redirect = flow_plan.get(next_redirect_key, '/assessment/')

        # Check if both assessments are complete
        if updated_session.status == 'COMPLETED':
            next_redirect = flow_plan.get('both_complete_redirect', '/assessment/')
            completion_message = "Semua assessment selesai! 🎉"
        else:
            next_assessment = 'LLM' if assessment_type == 'phq' else 'PHQ'
            completion_message = f"{assessment_type.upper()} selesai! Lanjut ke {next_assessment}..."

        return jsonify({
            "status": "OLKORECT",
            "assessment_completed": assessment_type,
            "session_status": updated_session.status,
            "next_redirect": next_redirect,
            "message": completion_message
        })

    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@assessment_bp.route('/sessions', methods=['GET'])
@login_required
@raw_response
def get_user_sessions():
    """Get all sessions for current user with status indicators"""
    try:
        sessions_with_status = SessionService.get_user_sessions_with_status(current_user.id)

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


@assessment_bp.route('/recover/<int:session_id>', methods=['POST'])
@login_required
@raw_response
def recover_session(session_id):
    """Recover an abandoned/incomplete session"""
    try:
        data = request.get_json() or {}
        clear_data = data.get('clear_data', True)  # Default to clearing data for fresh restart

        from ..services.session.sessionManager import SessionManager

        # Verify session belongs to current user
        session = SessionManager.get_session(session_id)
        if not session or session.user_id != current_user.id:
            return jsonify({"status": "SNAFU", "error": "Session not found or access denied"}), 403

        # Recover the session
        recovered_session = SessionManager.recover_session(session_id, clear_data=clear_data)

        return jsonify({
            "status": "OLKORECT",
            "message": "Session berhasil dipulihkan" if not clear_data else "Session berhasil direset untuk memulai ulang",
            "session_id": recovered_session.id,
            "session_status": recovered_session.status,
            "next_step": "consent" if clear_data else "assessment",
            "redirect_url": "/assessment/"
        })

    except ValueError as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@assessment_bp.route('/abandon/<int:session_id>', methods=['POST'])
@login_required
@raw_response
def abandon_session(session_id):
    """Mark session as abandoned (user quit)"""
    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'User abandoned session')

        from ..services.session.sessionManager import SessionManager

        # Verify session belongs to current user
        session = SessionManager.get_session(session_id)
        if not session or session.user_id != current_user.id:
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
