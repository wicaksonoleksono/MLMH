from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ..decorators import admin_required
from ..services.admin.adminService import AdminService

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard with system stats"""
    stats = AdminService.get_system_stats()
    recent_logs = AdminService.get_admin_logs(limit=10)
    return render_template('admin/dashboard.html', stats=stats, recent_logs=recent_logs)

@admin_bp.route('/settings')
@login_required
@admin_required
def settings():
    """System settings management"""
    category = request.args.get('category')
    settings = AdminService.get_system_settings(category)
    return render_template('admin/settings.html', settings=settings, current_category=category)

@admin_bp.route('/settings/update', methods=['POST'])
@login_required
@admin_required
def update_setting():
    """Update system setting"""
    try:
        key = request.form['key']
        value = request.form['value']
        
        result = AdminService.update_system_setting(
            key=key,
            value=value,
            admin_user=current_user.uname
        )
        
        flash(f'[OLKORECT] Setting {key} updated successfully', 'success')
        if result.get('requires_restart'):
            flash('[WATCHOUT] This setting requires application restart to take effect', 'warning')
            
    except ValueError as e:
        flash(f'[SNAFU] Error updating setting: {str(e)}', 'error')
    except Exception as e:
        flash(f'[SNAFU] Unexpected error: {str(e)}', 'error')
    
    return redirect(url_for('admin.settings'))

@admin_bp.route('/settings/create', methods=['POST'])
@login_required
@admin_required
def create_setting():
    """Create new system setting"""
    try:
        result = AdminService.create_system_setting(
            key=request.form['key'],
            value=request.form['value'],
            data_type=request.form['data_type'],
            category=request.form['category'],
            description=request.form['description'],
            admin_user=current_user.uname
        )
        
        flash(f'[OLKORECT] Setting {result["key"]} created successfully', 'success')
        
    except ValueError as e:
        flash(f'[SNAFU] Error creating setting: {str(e)}', 'error')
    except Exception as e:
        flash(f'[SNAFU] Unexpected error: {str(e)}', 'error')
    
    return redirect(url_for('admin.settings'))

@admin_bp.route('/assessments')
@login_required
@admin_required
def assessments():
    """Assessment configurations management"""
    assessment_type = request.args.get('type')
    configs = AdminService.get_assessment_configs(assessment_type)
    question_pools = AdminService.get_question_pools()
    return render_template('admin/assessments.html', configs=configs, 
                         question_pools=question_pools, current_type=assessment_type)

@admin_bp.route('/assessments/config/create', methods=['POST'])
@login_required
@admin_required
def create_assessment_config():
    """Create assessment configuration"""
    try:
        config_data = {}
        if request.form['assessment_type'] == 'PHQ':
            config_data = {
                'scoring_method': request.form.get('scoring_method', 'standard'),
                'interpretation_levels': {
                    'minimal': {'range': [0, 4], 'label': 'Minimal depression'},
                    'mild': {'range': [5, 9], 'label': 'Mild depression'},
                    'moderate': {'range': [10, 14], 'label': 'Moderate depression'},
                    'moderately_severe': {'range': [15, 19], 'label': 'Moderately severe'},
                    'severe': {'range': [20, 27], 'label': 'Severe depression'}
                },
                'auto_scoring': True
            }
        elif request.form['assessment_type'] == 'OpenQuestion':
            config_data = {
                'conversation_ending_keywords': request.form.get('ending_keywords', '').split(','),
                'max_duration_minutes': int(request.form.get('max_duration', 30)),
                'auto_transcription': True,
                'save_audio': True
            }
        elif request.form['assessment_type'] == 'Camera':
            config_data = {
                'capture_settings': {
                    'resolution': request.form.get('resolution', '1920x1080'),
                    'format': request.form.get('format', 'JPEG'),
                    'quality': int(request.form.get('quality', 85))
                },
                'analysis_enabled': request.form.get('analysis_enabled') == 'on',
                'auto_crop_face': request.form.get('auto_crop_face') == 'on'
            }
        
        result = AdminService.create_assessment_config(
            config_name=request.form['config_name'],
            assessment_type=request.form['assessment_type'],
            config_data=config_data,
            description=request.form['description'],
            admin_user=current_user.uname
        )
        
        flash(f'[OLKORECT] Assessment config {result["config_name"]} created successfully', 'success')
        
    except ValueError as e:
        flash(f'[SNAFU] Error creating config: {str(e)}', 'error')
    except Exception as e:
        flash(f'[SNAFU] Unexpected error: {str(e)}', 'error')
    
    return redirect(url_for('admin.assessments'))

@admin_bp.route('/media')
@login_required
@admin_required
def media():
    """Media settings management"""
    media_type = request.args.get('type')
    settings = AdminService.get_media_settings(media_type)
    return render_template('admin/media.html', settings=settings, current_type=media_type)

@admin_bp.route('/media/update', methods=['POST'])
@login_required
@admin_required
def update_media_setting():
    """Update media setting"""
    try:
        setting_id = int(request.form['setting_id'])
        updates = {}
        
        for key in ['max_file_size_mb', 'processing_timeout_seconds', 'retention_days']:
            if key in request.form and request.form[key]:
                updates[key] = int(request.form[key])
        
        for key in ['allowed_formats', 'storage_path']:
            if key in request.form and request.form[key]:
                updates[key] = request.form[key]
        
        if 'auto_process' in request.form:
            updates['auto_process'] = request.form['auto_process'] == 'on'
        
        if 'camera_settings' in request.form and request.form['camera_settings']:
            import json
            updates['camera_settings'] = json.loads(request.form['camera_settings'])
        
        result = AdminService.update_media_setting(
            setting_id=setting_id,
            updates=updates,
            admin_user=current_user.uname
        )
        
        flash(f'[OLKORECT] Media setting updated successfully', 'success')
        
    except ValueError as e:
        flash(f'[SNAFU] Error updating media setting: {str(e)}', 'error')
    except Exception as e:
        flash(f'[SNAFU] Unexpected error: {str(e)}', 'error')
    
    return redirect(url_for('admin.media'))

@admin_bp.route('/logs')
@login_required
@admin_required
def logs():
    """Admin action logs"""
    limit = min(int(request.args.get('limit', 50)), 500)
    admin_user = request.args.get('admin_user')
    logs = AdminService.get_admin_logs(limit=limit, admin_user=admin_user)
    return render_template('admin/logs.html', logs=logs, current_limit=limit, current_admin=admin_user)

@admin_bp.route('/api/stats')
@login_required
@admin_required
def api_stats():
    """API endpoint for dashboard stats"""
    stats = AdminService.get_system_stats()
    return jsonify(stats)