# app/routes/admin/llm_routes.py
from flask import Blueprint, request, jsonify, render_template
from flask_login import current_user
from ...services.admin.llmService import LLMService
from ...decorators import raw_response

llm_bp = Blueprint('llm', __name__, url_prefix='/admin/llm')


@llm_bp.route('/', methods=['GET'])
@raw_response
def llm_settings_page():
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    
    # Load actual settings from database
    settings_list = LLMService.get_settings()
    current_settings = settings_list[0] if settings_list else None
    
    # Try to load available models if API key exists
    available_models = []
    if current_settings and current_settings.get('openai_api_key'):
        try:
            available_models = LLMService.get_available_models()
        except Exception as e:
            # If models can't be loaded, just continue with empty list
            pass
    
    llm_data = {
        'settings': current_settings,
        'available_models': available_models
    }
    
    return render_template('admin/settings/llm/index.html', 
                         user=current_user,
                         llm_data=llm_data)


@llm_bp.route('/settings', methods=['GET'])
@raw_response
def get_settings():
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    return jsonify(LLMService.get_settings())


@llm_bp.route('/settings', methods=['POST'])
@raw_response
def create_settings():
    if not current_user.is_authenticated or not current_user.is_admin():
        return jsonify({"status": "SNAFU", "error": "Admin access required"}), 403
    try:
        data = request.get_json()
        result = LLMService.create_settings(
            openai_api_key=data.get('openai_api_key', ''),
            chat_model=data.get('chat_model', 'gpt-4o'),
            analysis_model=data.get('analysis_model', 'gpt-4o-mini'),
            depression_aspects=data.get('depression_aspects'),
            instructions=data.get('instructions'),
            is_default=True
        )
        return jsonify({"status": "OLKORECT", "data": result})
    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@llm_bp.route('/settings/<int:settings_id>', methods=['PUT'])
@raw_response
def update_settings(settings_id):
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    data = request.get_json()
    return jsonify(LLMService.update_settings(settings_id, data))


@llm_bp.route('/settings/<int:settings_id>', methods=['DELETE'])
@raw_response
def delete_settings(settings_id):
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    return jsonify(LLMService.delete_settings(settings_id))


@llm_bp.route('/settings/default', methods=['GET'])
@raw_response
def get_default_settings():
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    return jsonify(LLMService.get_default_settings())


@llm_bp.route('/models', methods=['GET'])
@raw_response
def get_available_models():
    """Get list of available OpenAI models"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    
    try:
        models = LLMService.get_available_models()
        return jsonify(models)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@llm_bp.route('/models/<model_id>/test', methods=['GET'])
@raw_response
def test_model(model_id):
    """Test if a specific model is available"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    
    try:
        available = LLMService.test_model_availability(model_id)
        return jsonify({"available": available})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@llm_bp.route('/prompt/build', methods=['POST'])
@raw_response  
def build_prompt():
    """Build system prompt from hard-coded template and aspects"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    
    data = request.get_json()
    aspects = data.get('aspects', [])
    
    try:
        prompt = LLMService.build_system_prompt(aspects)
        return jsonify({"prompt": prompt})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@llm_bp.route('/api-key/test', methods=['POST'])
@raw_response
def test_api_key():
    """Test OpenAI API key validity using stored encrypted key"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    
    try:
        # Get the actual LLMSettings object to access the decrypted API key
        from ...db import get_session
        from ...model.admin.llm import LLMSettings
        
        with get_session() as db:
            setting = db.query(LLMSettings).filter(LLMSettings.is_active == True).first()
            
            if not setting:
                return jsonify({"valid": False, "error": "No LLM settings found"})
            
            # Get decrypted API key from the model
            decrypted_api_key = setting.get_api_key()
            
            if not decrypted_api_key or decrypted_api_key.strip() == '':
                return jsonify({"valid": False, "error": "No API key configured"})
            
            # Test the decrypted API key
            valid = LLMService.test_api_key(decrypted_api_key)
            if valid:
                models = LLMService.get_available_models(decrypted_api_key)
                return jsonify({"valid": True, "models": models})
            else:
                return jsonify({"valid": False, "error": "Invalid API key"})
    except Exception as e:
        return jsonify({"valid": False, "error": str(e)})


@llm_bp.route('/config/default', methods=['GET'])
@raw_response
def get_default_config():
    """Get default configuration from environment"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    
    from flask import current_app
    return jsonify({
        "openai_api_key": current_app.config.get('OPENAI_API_KEY', ''),
        "default_chat_model": "gpt-4o",
        "default_analysis_model": "gpt-4o-mini"
    })