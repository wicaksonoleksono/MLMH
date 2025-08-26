# app/route/admin/phq_routes.py
from flask import Blueprint, request
from ...services.admin.phqService import PHQService
from ...decorators import admin_required, raw_response
phq_bp = Blueprint('phq', __name__, url_prefix='/admin/phq')


@phq_bp.route('/categories', methods=['GET'])
@admin_required
@raw_response
def get_categories():
    return PHQService.get_categories()


@phq_bp.route('/categories', methods=['POST'])
@admin_required
@raw_response
def create_category():
    data = request.get_json()
    return PHQService.create_category(
        name=data['name'],
        name_id=data['name_id'],
        description_en=data.get('description_en'),
        description_id=data.get('description_id'),
        order_index=data.get('order_index', 0)
    )


@phq_bp.route('/categories/<int:category_id>', methods=['PUT'])
@admin_required
@raw_response
def update_category(category_id):
    data = request.get_json()
    return PHQService.update_category(category_id, data)


@phq_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@admin_required
@raw_response
def delete_category(category_id):
    return PHQService.delete_category(category_id)


# ===== QUESTION ROUTES =====
@phq_bp.route('/questions', methods=['GET'])
@admin_required
@raw_response
def get_questions():
    category_id = request.args.get('category_id', type=int)
    return PHQService.get_questions(category_id)


@phq_bp.route('/questions', methods=['POST'])
@admin_required
@raw_response
def create_question():
    data = request.get_json()
    return PHQService.create_question(
        category_id=data['category_id'],
        question_text_en=data['question_text_en'],
        question_text_id=data['question_text_id'],
        order_index=data.get('order_index', 0)
    )


@phq_bp.route('/questions/<int:question_id>', methods=['PUT'])
@admin_required
@raw_response
def update_question(question_id):
    data = request.get_json()
    return PHQService.update_question(question_id, data)


@phq_bp.route('/questions/<int:question_id>', methods=['DELETE'])
@admin_required
@raw_response
def delete_question(question_id):
    return PHQService.delete_question(question_id)


# ===== SCALE ROUTES =====
@phq_bp.route('/scales', methods=['GET'])
@admin_required
@raw_response
def get_scales():
    return PHQService.get_scales()


@phq_bp.route('/scales', methods=['POST'])
@admin_required
@raw_response
def create_scale():
    data = request.get_json()
    return PHQService.create_scale(
        scale_name=data['scale_name'],
        min_value=data['min_value'],
        max_value=data['max_value'],
        scale_labels=data['scale_labels'],
        is_default=data.get('is_default', False)
    )


@phq_bp.route('/scales/<int:scale_id>', methods=['PUT'])
@admin_required
@raw_response
def update_scale(scale_id):
    data = request.get_json()
    return PHQService.update_scale(scale_id, data)


@phq_bp.route('/scales/<int:scale_id>', methods=['DELETE'])
@admin_required
@raw_response
def delete_scale(scale_id):
    return PHQService.delete_scale(scale_id)


# ===== SETTINGS ROUTES =====
@phq_bp.route('/settings', methods=['GET'])
@admin_required
@raw_response
def get_settings():
    return PHQService.get_settings()


@phq_bp.route('/settings', methods=['POST'])
@admin_required
@raw_response
def create_settings():
    data = request.get_json()
    return PHQService.create_settings(
        setting_name=data['setting_name'],
        questions_per_category=data['questions_per_category'],
        scale_id=data['scale_id'],
        randomize_questions=data.get('randomize_questions', False),
        is_default=data.get('is_default', False)
    )


@phq_bp.route('/settings/<int:settings_id>', methods=['PUT'])
@admin_required
@raw_response
def update_settings(settings_id):
    data = request.get_json()
    return PHQService.update_settings(settings_id, data)


@phq_bp.route('/settings/<int:settings_id>', methods=['DELETE'])
@admin_required
@raw_response
def delete_settings(settings_id):
    return PHQService.delete_settings(settings_id)
