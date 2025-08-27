# app/routes/assessment_routes.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import current_user, login_required
from ..decorators import raw_response
from ..services.sessionService import SessionService
from ..services.admin.consentService import ConsentService

assessment_bp = Blueprint('assessment', __name__, url_prefix='/assessment')


@assessment_bp.route('/start', methods=['POST'])
@login_required
@raw_response
def start_assessment():
    """Create new assessment session"""
    try:
        # Check if user can create session
        if not SessionService.can_create_session(current_user.id):
            return jsonify({
                "status": "SNAFU",
                "error": f"Maksimal {SessionService.MAX_SESSIONS_PER_USER} sesi per pengguna"
            }), 400

        # Create new session
        session = SessionService.create_session(current_user.id)

        return jsonify({
            "status": "OLKORECT",
            "session_id": session.id,
            "session_token": session.session_token,
            "is_first": session.is_first
        })

    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@assessment_bp.route('/')
@login_required
@raw_response
def assessment_dashboard():
    """Assessment dashboard - shows consent, then camera check"""
    # Check for active session
    active_session = SessionService.get_active_session(current_user.id)

    if not active_session:
        return redirect(url_for('main.serve_index'))

    return render_template('assessment/dashboard.html',
                           user=current_user,
                           session=active_session)


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
    active_session = SessionService.get_active_session(current_user.id)

    if not active_session:
        return redirect(url_for('main.serve_index'))
    
    # Check if ready for PHQ assessment
    if not active_session.consent_completed_at:
        return redirect(url_for('assessment.consent_page'))
    
    # Check session should start with PHQ
    if active_session.is_first != 'phq':
        return redirect(url_for('assessment.llm_assessment'))

    return render_template('assessment/phq.html',
                           user=current_user,
                           session=active_session)


@assessment_bp.route('/llm')
@login_required
@raw_response
def llm_assessment():
    """LLM Chat Assessment Page"""
    active_session = SessionService.get_active_session(current_user.id)

    if not active_session:
        return redirect(url_for('main.serve_index'))
    
    # Check if ready for LLM assessment
    if not active_session.consent_completed_at:
        return redirect(url_for('assessment.consent_page'))
    
    # Check session should start with LLM
    if active_session.is_first != 'llm':
        return redirect(url_for('assessment.phq_assessment'))

    return render_template('assessment/llm.html',
                           user=current_user,
                           session=active_session)
