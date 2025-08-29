# app/routes/assessment_routes.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import current_user, login_required
from ..decorators import raw_response
from ..services.sessionService import SessionService

assessment_bp = Blueprint('assessment', __name__, url_prefix='/assessment')


@assessment_bp.route('/start', methods=['POST'])
@login_required
def start_assessment():
    """Create new assessment session with intelligent recovery handling"""
    try:
        # Smart session creation - check for recoverable sessions first
        from ..services.session.sessionManager import SessionManager
        
        recoverable_session = SessionManager.get_user_recoverable_session(current_user.id)
        
        if recoverable_session:
            # User has recoverable session - reset it instead of creating new one
            print(f"🔄 Found recoverable session {recoverable_session.id}, resetting instead of creating new")
            reset_result = SessionService.reset_session_to_new_attempt(
                recoverable_session.id, 
                "AUTO_RECOVERY_ON_NEW_START"
            )
            
            if reset_result['success']:
                print(f"✅ Successfully reset recoverable session to new attempt")
                flash('Sesi sebelumnya telah direset. Memulai assessment baru.', 'success')
                return redirect(url_for('assessment.assessment_dashboard'))
            else:
                print(f"❌ Failed to reset recoverable session: {reset_result.get('message')}")
                flash('Gagal mereset sesi sebelumnya.', 'error')
                return redirect(url_for('main.serve_index'))

        # Check if user can create new session
        if not SessionService.can_create_new_session(current_user.id):
            flash('Anda sudah mencapai maksimum 2 sesi assessment.', 'error')
            return redirect(url_for('main.serve_index'))

        # Create new session with improved system
        session = SessionService.create_session(current_user.id)
        print(f"✅ Created new session {session.id}")
        
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
        print(f"❌ Error creating session: {str(e)}")
        flash('Terjadi kesalahan sistem. Silakan coba lagi.', 'error')
        return redirect(url_for('main.serve_index'))


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
    
    print(f"🏠 Dashboard - session_id={session.id}, status={session.status}, phq_completed={session.phq_completed_at}, llm_completed={session.llm_completed_at}, is_first={session.is_first}")

    # Direct redirect logic based on session flow
    if not session.consent_completed_at:
        print(" No consent - redirecting to consent")
        return redirect(url_for('assessment.consent_page'))

    if session.status == 'CONSENT' and not session.camera_completed:
        print(" No camera check - redirecting to camera")
        return redirect(url_for('assessment.camera_check'))
    
    # Handle CAMERA_CHECK status properly
    if session.status == 'CAMERA_CHECK' and not session.camera_completed:
        print("📷 Camera check incomplete - redirecting to camera check")
        return redirect(url_for('assessment.camera_check'))

    # Direct redirect logic for assessments - automatic flow
    if session.status in ['PHQ_IN_PROGRESS', 'LLM_IN_PROGRESS', 'BOTH_IN_PROGRESS']:
        next_assessment = session.next_assessment_type
        print(f"📋 Session in progress - next_assessment: {next_assessment}")
        if next_assessment == 'phq':
            print("➡️ Redirecting to PHQ")
            return redirect(url_for('assessment.phq_assessment'))
        elif next_assessment == 'llm':
            print("➡️ Redirecting to LLM")
            return redirect(url_for('assessment.llm_assessment'))

    # If camera check is done but no assessment started, start first assessment
    if session.status == 'CAMERA_CHECK' and session.camera_completed:
        print(f"📷 Camera check done - starting first assessment: {session.is_first}")
        if session.is_first == 'phq':
            return redirect(url_for('assessment.phq_assessment'))
        else:
            return redirect(url_for('assessment.llm_assessment'))
    
    # If session is completed, show completed dashboard
    if session.status == 'COMPLETED':
        print("🎉 Session completed - showing dashboard")
    else:
        print(f"⚠️ Unexpected dashboard state - status: {session.status}")

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

    # If session is already in PHQ_IN_PROGRESS or LLM_IN_PROGRESS, camera check is implied to be done
    if session.status in ['CREATED', 'CONSENT', 'CAMERA_CHECK'] and not session.camera_completed:
        return redirect(url_for('assessment.camera_check'))

    # If camera check just completed, transition session status to proper assessment status
    if session.status == 'CAMERA_CHECK' and session.camera_completed:
        if session.is_first == 'phq':
            SessionService.complete_camera_check(session.id)
            session = SessionService.get_session(session.id)
        else:
            # PHQ is not first, redirect to LLM
            return redirect(url_for('assessment.llm_assessment'))
    next_assessment = session.next_assessment_type
    if next_assessment != 'phq':
        if next_assessment == 'llm':
            return redirect(url_for('assessment.llm_assessment'))
        elif session.status == 'COMPLETED':
            return redirect(url_for('assessment.assessment_dashboard'))
        else:
            return redirect(url_for('assessment.assessment_dashboard'))
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

    # If session is already in PHQ_IN_PROGRESS or LLM_IN_PROGRESS, camera check is implied to be done
    if session.status in ['CREATED', 'CONSENT', 'CAMERA_CHECK'] and not session.camera_completed:
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
            return redirect(url_for('assessment.assessment_dashboard'))
    return render_template('assessment/llm.html',
                           user=current_user,
                           session=session)


@assessment_bp.route('/complete/<assessment_type>/<session_id>', methods=['POST'])
@login_required
@raw_response
def complete_assessment(assessment_type, session_id):
    """Universal completion handler for any assessment type"""
    session = SessionService.get_session(session_id)

    # Complete the specified assessment
    if assessment_type == 'phq':
        SessionService.complete_phq_assessment(session.id)
    elif assessment_type == 'llm':
        SessionService.complete_llm_assessment(session.id)
    else:
        return jsonify({"status": "SNAFU", "error": "Invalid assessment type"}), 400

    # Get updated session and flow plan
    updated_session = SessionService.get_session(session.id)
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
    """Reset session to new attempt with version increment (using UUID)"""
    try:
        session = SessionService.get_session(session_id)
        if not session:
            flash('Session tidak ditemukan.', 'error')
            return redirect(url_for('main.serve_index'))
        
        # Verify session belongs to current user
        if int(session.user_id) != int(current_user.id):
            flash('Akses ditolak.', 'error')
            return redirect(url_for('main.serve_index'))
        
        reason = request.form.get('reason', 'USER_INITIATED_RESET')
        result = SessionService.reset_session_to_new_attempt(session.id, reason)
        
        flash(f'Session berhasil direset. Memulai assessment baru.', 'success')
        return redirect(url_for('assessment.assessment_dashboard'))
        
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('main.serve_index'))
    except Exception as e:
        print(f"❌ Error resetting session: {str(e)}")
        flash('Terjadi kesalahan sistem. Silakan coba lagi.', 'error')
        return redirect(url_for('main.serve_index'))


@assessment_bp.route('/recover/<session_id>', methods=['POST'])
@login_required
def recover_session(session_id):
    """Continue or reset a recoverable session"""
    try:
        session = SessionService.get_session(session_id)
        if not session:
            flash('Session tidak ditemukan.', 'error')
            return redirect(url_for('main.serve_index'))
        
        # Verify session belongs to current user
        if int(session.user_id) != int(current_user.id):
            flash('Akses ditolak.', 'error')
            return redirect(url_for('main.serve_index'))
        
        clear_data = request.form.get('clear_data', 'false').lower() == 'true'
        
        if clear_data:
            # Reset the session (clear data and start fresh)
            result = SessionService.reset_session_to_new_attempt(session.id, "USER_RECOVERY_RESET")
            flash('Session direset. Memulai assessment baru.', 'success')
        else:
            # Continue the session (just reactivate)
            session = SessionService.recover_session(session.id, clear_data=False)
            flash('Melanjutkan assessment sebelumnya.', 'info')
        
        return redirect(url_for('assessment.assessment_dashboard'))
        
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('main.serve_index'))
    except Exception as e:
        print(f"❌ Error recovering session: {str(e)}")
        flash('Terjadi kesalahan sistem. Silakan coba lagi.', 'error')
        return redirect(url_for('main.serve_index'))

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


@assessment_bp.route('/recover/<session_id>', methods=['POST'])
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
        if not session or int(session.user_id) != int(current_user.id):
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


@assessment_bp.route('/abandon/<session_id>', methods=['POST'])
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
