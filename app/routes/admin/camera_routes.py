# app/routes/admin/camera_routes.py
from flask import Blueprint, request, jsonify, render_template
from flask_login import current_user
from ...services.admin.cameraService import CameraService
from ...decorators import raw_response

camera_bp = Blueprint('camera', __name__, url_prefix='/admin/camera')


@camera_bp.route('/', methods=['GET'])
@raw_response
def camera_settings_page():
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    return render_template('admin/settings/camera/index.html', user=current_user)


@camera_bp.route('/settings', methods=['GET'])
@raw_response
def get_settings():
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    return jsonify(CameraService.get_settings())


@camera_bp.route('/settings', methods=['POST'])
@raw_response
def create_settings():
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    data = request.get_json()
    return jsonify(CameraService.create_settings(
        recording_mode=data['recording_mode'],
        storage_path=data.get('storage_path', 'recordings'),
        interval_seconds=data.get('interval_seconds'),
        resolution=data.get('resolution', '1280x720'),
        capture_on_button_click=data.get('capture_on_button_click', True),
        capture_on_message_send=data.get('capture_on_message_send', False),
        capture_on_question_start=data.get('capture_on_question_start', False),
        is_default=data.get('is_default', False)
    ))


@camera_bp.route('/settings/<int:settings_id>', methods=['PUT'])
@raw_response
def update_settings(settings_id):
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    data = request.get_json()
    return jsonify(CameraService.update_settings(settings_id, data))


@camera_bp.route('/settings/<int:settings_id>', methods=['DELETE'])
@raw_response
def delete_settings(settings_id):
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    return jsonify(CameraService.delete_settings(settings_id))


@camera_bp.route('/settings/default', methods=['GET'])
@raw_response
def get_default_settings():
    if not current_user.is_authenticated or not current_user.is_admin():
        return {"status": "SNAFU", "error": "Admin access required"}, 403
    return jsonify(CameraService.get_default_settings())