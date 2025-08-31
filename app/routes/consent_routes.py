# app/routes/consent_routes.py
from flask import Blueprint, jsonify
from flask_login import current_user, login_required
from ..decorators import raw_response
from ..services.admin.consentService import ConsentService

consent_bp = Blueprint('consent', __name__, url_prefix='/consent')


@consent_bp.route('/form', methods=['GET'])
@login_required
@raw_response
def get_consent_form():
    """Get consent form for user"""
    db_settings = ConsentService.get_settings()
    
    if not db_settings:
        return jsonify({"error": "Consent settings not configured"}), 400
    
    setting = db_settings[0]  # Get first active setting
    consent_data = {
        'title': setting.get('title', ''),
        'content': setting.get('content', ''),
        'footer_text': setting.get('footer_text', '')
    }
    
    return jsonify(consent_data)