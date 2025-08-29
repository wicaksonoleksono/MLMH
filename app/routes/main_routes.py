from flask import Blueprint, request, render_template, redirect, url_for
from flask_login import current_user, login_required
from ..decorators import raw_response
from ..services.sessionService import SessionService
from ..services.admin.statsService import StatsService

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@raw_response
def serve_index():
    """Main dashboard - admin or user based on role."""
    if current_user.is_authenticated:
        if current_user.is_admin():
            stats = StatsService.get_dashboard_stats()
            user_sessions = StatsService.get_user_sessions_preview()
            return render_template("admin/dashboard.html", user=current_user, stats=stats, user_sessions=user_sessions)
        else:
            return render_template("user/dashboard.html", user=current_user)
    return redirect(url_for('main.auth_page'))

@main_bp.route('/auth')
@raw_response
def auth_page():
    """Authentication page (login/register)."""
    if current_user.is_authenticated:
        return redirect(url_for('main.serve_index'))

    return render_template('auth/login_register.html')


@main_bp.route('/error/settings-not-configured')
@login_required
@raw_response
def settings_not_configured():
    """Error page for missing assessment settings"""
    settings_check = SessionService.check_assessment_settings_configured()
    return render_template('error/settings_not_configured.html', 
                         missing_settings=settings_check['missing_settings'])
