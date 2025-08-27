# app/route/admin/phq_routes.py
from flask import Blueprint, request, jsonify
from flask_login import current_user
from ...services.admin.phqService import PHQService
from ...decorators import raw_response
phq_bp = Blueprint('phq', __name__, url_prefix='/admin/phq')


@phq_bp.route('/categories', methods=['GET'])
@raw_response
def get_categories():
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    return jsonify(PHQService.get_categories())





# ===== QUESTION ROUTES =====
@phq_bp.route('/questions', methods=['GET'])
@raw_response
def get_questions():
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    category_name_id = request.args.get('category_name_id')
    return jsonify(PHQService.get_questions(category_name_id))


@phq_bp.route('/questions', methods=['POST'])
@raw_response
def create_question():
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    data = request.get_json()
    return jsonify(PHQService.create_question(
        category_name_id=data['category_name_id'],
        question_text_en=data['question_text_en'],
        question_text_id=data['question_text_id'],
        order_index=data.get('order_index', 0)
    ))


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
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    return jsonify(PHQService.get_scales())


@phq_bp.route('/scales', methods=['POST'])
@raw_response
def create_scale():
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    data = request.get_json()
    return jsonify(PHQService.create_scale(
        scale_name=data['scale_name'],
        min_value=data['min_value'],
        max_value=data['max_value'],
        scale_labels=data['scale_labels'],
        is_default=data.get('is_default', False)
    ))


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
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    return jsonify(PHQService.get_settings())


@phq_bp.route('/settings', methods=['POST'])
@raw_response
def create_settings():
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    data = request.get_json()
    return jsonify(PHQService.create_settings(
        setting_name=data['setting_name'],
        questions_per_category=data['questions_per_category'],
        scale_id=data['scale_id'],
        randomize_questions=data.get('randomize_questions', False),
        instructions=data.get('instructions'),
        is_default=data.get('is_default', False)
    ))


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
