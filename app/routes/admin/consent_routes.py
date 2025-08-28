# app/routes/admin/consent_routes.py
from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user
from ...decorators import raw_response, admin_required
from ...services.admin.consentService import ConsentService
consent_bp = Blueprint('admin_consent', __name__, url_prefix='/admin/consent')


@consent_bp.route('/')
@admin_required
def index():
    """Consent settings page"""
    from flask_login import current_user
    return render_template('admin/settings/consent/index.html', user=current_user)


@consent_bp.route('/settings', methods=['GET'])
@raw_response
def get_settings():
    """Get all consent settings"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    return jsonify(ConsentService.get_settings())


@consent_bp.route('/settings', methods=['POST'])
@raw_response
def create_settings():
    """Create or update consent settings"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    data = request.get_json()

    return jsonify(ConsentService.create_settings(
        title=data['title'],
        content=data['content'],
        require_signature=data.get('require_signature', False),
        require_date=data.get('require_date', False),
        allow_withdrawal=data.get('allow_withdrawal', False),
        footer_text=data.get('footer_text'),
        is_default=data.get('is_default', False)
    ))


@consent_bp.route('/settings/<int:settings_id>', methods=['PUT'])
@raw_response
def update_settings(settings_id):
    """Update consent settings"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    data = request.get_json()
    return jsonify(ConsentService.update_settings(settings_id, data))


@consent_bp.route('/settings/<int:settings_id>', methods=['DELETE'])
@raw_response
def delete_settings(settings_id):
    """Delete consent settings"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    return jsonify(ConsentService.delete_settings(settings_id))


@consent_bp.route('/settings/default', methods=['GET'])
@raw_response
def get_default_settings():
    """Get default consent settings"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    return jsonify(ConsentService.get_default_settings())
