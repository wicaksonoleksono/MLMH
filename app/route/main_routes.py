from flask import Blueprint, request, render_template, redirect, url_for
from flask_login import current_user, login_required
from ..decorators import raw_response

main_bp = Blueprint('main', __name__)




@main_bp.route('/')
@raw_response
def serve_index():
    """Main landing page with authentication check."""
    # If user is authenticated, show dashboard
    if current_user.is_authenticated:
        return render_template('landing.html', user=current_user)
    
    # If not authenticated, redirect to auth page
    return redirect(url_for('main.auth_page'))


@main_bp.route('/auth')
@raw_response 
def auth_page():
    """Authentication page (login/register)."""
    # If already authenticated, redirect to main
    if current_user.is_authenticated:
        return redirect(url_for('main.serve_index'))
    
    return render_template('auth/login_register.html')


@main_bp.route('/dashboard')
@login_required
@raw_response
def dashboard():
    """User dashboard after login."""
    return render_template('user/dashboard.html', user=current_user)