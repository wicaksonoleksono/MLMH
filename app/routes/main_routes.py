from flask import Blueprint, request, render_template, redirect, url_for
from flask_login import current_user, login_required
from ..decorators import raw_response
from ..services.session.sessionManager import SessionManager
from ..services.admin.statsService import StatsService

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@raw_response
def serve_index():
    """Main dashboard - admin or user based on role."""
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for('admin.dashboard'))
        else:
            return render_template("user/dashboard.html", user=current_user)
    return redirect(url_for('main.auth_page'))

@main_bp.route('/auth')
def auth_page():
    """Redirect to login page."""
    return redirect(url_for('auth.login'))


@main_bp.route('/error/settings-not-configured')
@login_required
@raw_response
def settings_not_configured():
    """Error page for missing assessment settings"""
    settings_check = SessionManager.check_assessment_settings_configured()
    return render_template('error/settings_not_configured.html', 
                         missing_settings=settings_check['missing_settings'])


@main_bp.route('/mobile-restriction')
@raw_response
def mobile_restriction():
    """Mobile restriction page for phone/tablet users"""
    return render_template('mobile_restriction.html')
