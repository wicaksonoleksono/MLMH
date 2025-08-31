"""Admin profile routes for managing admin user profiles."""

from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user
from app.services.shared.user_service import UserService
from app.decorators import login_required, admin_required

# Create blueprint
bp = Blueprint('admin_profile', __name__, url_prefix='/admin/profile')


@bp.route('/')
@admin_required
def profile():
    """Render the admin profile page."""
    # Use current_user from Flask-Login instead of session
    return render_template('admin/profile.html', user=current_user)


@bp.route('/update', methods=['POST'])
@admin_required
def update_profile():
    """Update admin profile information."""
    user_id = int(current_user.id)  # Convert string ID to integer
    
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')

    # Validate input
    if not username:
        return jsonify({"status": "SNAFU", "error": "Username is required"}), 400

    # Update profile using service
    result = UserService.update_profile(user_id, username, email)
    return jsonify(result)


@bp.route('/update-password', methods=['POST'])
@admin_required
def update_password():
    """Update admin password."""
    user_id = int(current_user.id)  # Convert string ID to integer
    
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    # Validate input
    if not current_password or not new_password:
        return jsonify({"status": "SNAFU", "error": "Current and new passwords are required"}), 400

    if len(new_password) < 6:
        return jsonify({"status": "SNAFU", "error": "Password must be at least 6 characters"}), 400

    # Update password using service
    result = UserService.update_password(user_id, current_password, new_password)
    return jsonify(result)