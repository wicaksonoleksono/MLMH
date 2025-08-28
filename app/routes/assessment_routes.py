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
        
    # Direct redirect logic for assessments - no intermediate page
    if session.status in ['PHQ_IN_PROGRESS', 'LLM_IN_PROGRESS', 'BOTH_IN_PROGRESS']:
        next_assessment = session.next_assessment_type
        if next_assessment == 'phq':
            return redirect(url_for('assessment.phq_assessment'))
        elif next_assessment == 'llm':
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
    # Check if settings are configured
    settings_check = SessionService.check_assessment_settings_configured()
    if not settings_check['all_configured']:
        return redirect(url_for('main.settings_not_configured'))
    
    active_session = SessionService.get_active_session(current_user.id)

    if not active_session:
        return redirect(url_for('main.serve_index'))
    
    session = active_session
    
    # Check prerequisites for assessment
    if not session.consent_completed_at:
        return redirect(url_for('assessment.consent_page'))
    
    if not session.camera_completed:
        return redirect(url_for('assessment.camera_check'))
    
    # If camera check just completed, transition session status to proper assessment status
    if session.status == 'CAMERA_CHECK' and session.camera_completed:
        if session.is_first == 'llm':
            SessionService.complete_camera_check(session.id)
            # Refresh session after status change
            session = SessionService.get_session(session.id)
        else:
            # LLM is not first, redirect to PHQ
            return redirect(url_for('assessment.phq_assessment'))
    
    # Check session should do LLM now based on status and completion
    next_assessment = session.next_assessment_type
    if next_assessment != 'llm':
        if next_assessment == 'phq':
            return redirect(url_for('assessment.phq_assessment'))
        elif session.status == 'COMPLETED':
            return redirect(url_for('assessment.assessment_dashboard'))
        else:
            # Unknown state, go to dashboard
            return redirect(url_for('assessment.assessment_dashboard'))

    return render_template('assessment/llm.html',
                           user=current_user,
                           session=session)




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
