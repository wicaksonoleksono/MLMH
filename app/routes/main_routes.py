from flask import Blueprint, request, render_template, redirect, url_for
from flask_login import current_user, login_required
from ..decorators import raw_response

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@raw_response
def serve_index():
    """Main landing page with authentication check."""
    if current_user.is_authenticated:
        template = "admin/landing.html" if current_user.is_admin else "user/landing.html"
        return render_template(template, user=current_user)
    return redirect(url_for('main.auth_page'))


@main_bp.route('/auth')
@raw_response
def auth_page():
    """Authentication page (login/register)."""
    if current_user.is_authenticated:
        return redirect(url_for('main.serve_index'))

    return render_template('auth/login_register.html')


@main_bp.route('/dashboard')
@login_required
@raw_response
def dashboard():
    """User dashboard after login."""
    return render_template('user/dashboard.html', user=current_user)


@main_bp.route('/admin/phq')
@login_required
@raw_response
def admin_phq():
    """PHQ settings page for admin."""
    if not current_user.is_admin:
        return redirect(url_for('main.serve_index'))
    return render_template('admin/settings/phq/index.html', user=current_user)
