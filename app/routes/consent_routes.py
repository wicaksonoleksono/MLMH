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
    settings = ConsentService.get_default_settings()
    
    # Remove signature requirement and form settings fields
    consent_data = {
        'title': settings.get('title', ''),
        'content': settings.get('content', ''),
        'footer_text': settings.get('footer_text', ''),
        'allow_withdrawal': settings.get('allow_withdrawal', True)
    }
    
    return jsonify(consent_data)