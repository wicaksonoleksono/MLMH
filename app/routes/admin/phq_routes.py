# app/route/admin/phq_routes.py
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import current_user
from ...services.admin.phqService import PHQService
from ...decorators import raw_response
phq_bp = Blueprint('phq', __name__, url_prefix='/admin/phq')


# ===== MAIN SETTINGS PAGE =====
@phq_bp.route('/settings', methods=['GET'])
@raw_response  
def phq_settings_page():
    """PHQ Settings page with clean data flow from service layer"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return redirect(url_for('main.auth_page'))
    
    # Get complete PHQ data structure from service layer (single source of truth)
    try:
        phq_data = PHQService.get_complete_default_structure()
    except Exception as e:
        # Fallback to basic structure if error
        phq_data = {
            'categories': PHQService.get_default_categories(),
            'questions_by_category': {},
            'scale': None,
            'settings': None
        }
    
    return render_template('admin/settings/phq/index.html', 
                         user=current_user,
                         phq_data=phq_data)


@phq_bp.route('/settings/save', methods=['POST'])
@raw_response
def save_all_settings():
    """Save all PHQ settings in one clean server-side operation - NO MORE AJAX HELL!"""
    if not current_user.is_authenticated or not current_user.is_admin():
        flash('Admin access required', 'error')
        return redirect(url_for('main.auth_page'))
    
    try:
        # Extract form data
        scale_name = request.form.get('scale_name', 'PHQ-9 Default')
        min_value = int(request.form.get('min_value', 0))
        max_value = int(request.form.get('max_value', 3))
        
        # Build scale_labels from form data
        scale_labels = {}
        for i in range(min_value, max_value + 1):
            label_key = f'scale_label_{i}'
            scale_labels[str(i)] = request.form.get(label_key, f'Label {i}')
        
        # Save scale (this will update existing default)
        scale_result = PHQService.create_scale(
            scale_name=scale_name,
            min_value=min_value,
            max_value=max_value,
            scale_labels=scale_labels,
            is_default=True
        )
        
        # Process questions for each category
        categories = ['ANHEDONIA', 'DEPRESSED_MOOD', 'SLEEP_DISTURBANCE', 'FATIGUE', 
                     'APPETITE_CHANGE', 'GUILT', 'CONCENTRATION', 'PSYCHOMOTOR', 'SUICIDAL_IDEATION']
        
        for category in categories:
            # Get questions for this category from form
            questions = []
            i = 0
            while True:
                question_key = f'question_{category}_{i}'
                question_text = request.form.get(question_key)
                if not question_text or not question_text.strip():
                    break
                questions.append(question_text.strip())
                i += 1
            
            # Delete existing questions for category
            existing = PHQService.get_questions(category)
            for q in existing:
                PHQService.delete_question(q['id'])
            
            # Create new questions
            for idx, question_text in enumerate(questions):
                PHQService.create_question(
                    category_name_id=category,
                    question_text_en=question_text,
                    question_text_id=question_text,
                    order_index=idx
                )
        
        # Create/update settings
        randomize = request.form.get('randomize_questions') == 'on'
        instructions = request.form.get('instructions', '')
        
        PHQService.create_settings(
            scale_id=scale_result['id'],
            randomize_categories=randomize,
            instructions=instructions,
            is_default=True
        )
        
        flash('PHQ settings saved successfully!', 'success')
        return redirect(url_for('phq.phq_settings_page'))
        
    except Exception as e:
        flash(f'Error saving PHQ settings: {str(e)}', 'error')
        return redirect(url_for('phq.phq_settings_page'))


@phq_bp.route('/api/defaults', methods=['POST'])
@raw_response
def load_phq_defaults_ajax():
    """Load PHQ default questions from enum into database"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return jsonify({"status": "SNAFU", "error": "Admin access required"}), 403
    
    try:
        # Get default categories with their default questions from enum
        default_categories = PHQService.get_default_categories()
        
        # Clear existing questions for all categories first
        existing_questions = PHQService.get_questions()
        for q in existing_questions:
            PHQService.delete_question(q['id'])
        
        # Load default questions from enum for each category
        for default_cat in default_categories:
            for idx, question_text in enumerate(default_cat['default_questions']):
                PHQService.create_question(
                    category_name_id=default_cat['name_id'],
                    question_text_en=question_text,
                    question_text_id=question_text,
                    order_index=idx
                )
        
        return jsonify({"status": "OLKORECT", "message": "PHQ defaults loaded successfully"})
    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@phq_bp.route('/categories', methods=['GET'])
@raw_response
def get_categories():
    if not current_user.is_authenticated or not current_user.is_admin():
        return jsonify({"status": "SNAFU", "error": "Admin access required"}), 403
    try:
        result = PHQService.get_categories()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500





# ===== QUESTION ROUTES =====
@phq_bp.route('/questions', methods=['GET'])
@raw_response
def get_questions():
    if not current_user.is_authenticated or not current_user.is_admin():
        return jsonify({"status": "SNAFU", "error": "Admin access required"}), 403
    try:
        category_name_id = request.args.get('category_name_id')
        result = PHQService.get_questions(category_name_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@phq_bp.route('/questions', methods=['POST'])
@raw_response
def create_question():
    if not current_user.is_authenticated or not current_user.is_admin():
        return jsonify({"status": "SNAFU", "error": "Admin access required"}), 403
    try:
        data = request.get_json()
        result = PHQService.create_question(
            category_name_id=data['category_name_id'],
            question_text_en=data['question_text_en'],
            question_text_id=data['question_text_id'],
            order_index=data.get('order_index', 0)
        )
        return jsonify({"status": "OLKORECT", "data": result})
    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@phq_bp.route('/questions/<int:question_id>', methods=['PUT'])
@raw_response
def update_question(question_id):
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    data = request.get_json()
    return jsonify(PHQService.update_question(question_id, data))


@phq_bp.route('/questions/<int:question_id>', methods=['DELETE'])
@raw_response
def delete_question(question_id):
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    return jsonify(PHQService.delete_question(question_id))


# ===== SCALE ROUTES =====
@phq_bp.route('/scales', methods=['GET'])
@raw_response
def get_scales():
    if not current_user.is_authenticated or not current_user.is_admin():
        return jsonify({"status": "SNAFU", "error": "Admin access required"}), 403
    try:
        result = PHQService.get_scales()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@phq_bp.route('/scales', methods=['POST'])
@raw_response
def create_scale():
    if not current_user.is_authenticated or not current_user.is_admin():
        return jsonify({"status": "SNAFU", "error": "Admin access required"}), 403
    try:
        data = request.get_json()
        result = PHQService.create_scale(
            scale_name=data['scale_name'],
            min_value=data['min_value'],
            max_value=data['max_value'],
            scale_labels=data['scale_labels'],
            is_default=data.get('is_default', False)
        )
        return jsonify({"status": "OLKORECT", "data": result})
    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@phq_bp.route('/scales/<int:scale_id>', methods=['PUT'])
@raw_response
def update_scale(scale_id):
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    data = request.get_json()
    return jsonify(PHQService.update_scale(scale_id, data))


@phq_bp.route('/scales/<int:scale_id>', methods=['DELETE'])
@raw_response
def delete_scale(scale_id):
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    return jsonify(PHQService.delete_scale(scale_id))


# ===== SETTINGS ROUTES =====
@phq_bp.route('/settings', methods=['GET'])
@raw_response
def get_settings():
    if not current_user.is_authenticated or not current_user.is_admin():
        return jsonify({"status": "SNAFU", "error": "Admin access required"}), 403
    try:
        result = PHQService.get_settings()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@phq_bp.route('/settings', methods=['POST'])
@raw_response
def create_settings():
    if not current_user.is_authenticated or not current_user.is_admin():
        return jsonify({"status": "SNAFU", "error": "Admin access required"}), 403
    try:
        data = request.get_json()
        result = PHQService.create_settings(
            scale_id=data['scale_id'],
            randomize_categories=data.get('randomize_questions', False),
            instructions=data.get('instructions'),
            is_default=data.get('is_default', False)
        )
        return jsonify({"status": "OLKORECT", "data": result})
    except Exception as e:
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@phq_bp.route('/settings/<int:settings_id>', methods=['PUT'])
@raw_response
def update_settings(settings_id):
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    data = request.get_json()
    return jsonify(PHQService.update_settings(settings_id, data))


@phq_bp.route('/settings/<int:settings_id>', methods=['DELETE'])
@raw_response
def delete_settings(settings_id):
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    return jsonify(PHQService.delete_settings(settings_id))
