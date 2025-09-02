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
        # Return default settings if no active settings found
        default_settings = ConsentService.get_default_settings()
        consent_data = {
            'title': default_settings.get('title', ''),
            'content': default_settings.get('content', ''),
            'footer_text': default_settings.get('footer_text', '')
        }
    else:
        # Get first active setting
        setting = db_settings[0]
        consent_data = {
            'title': setting.get('title', ''),
            'content': setting.get('content', ''),
            'footer_text': setting.get('footer_text', '')
        }
    
    return jsonify(consent_data)