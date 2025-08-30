# app/routes/admin_routes.py
from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required
from ..decorators import raw_response, admin_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/')
@login_required
@admin_required
@raw_response
def dashboard():
    """Admin dashboard"""
    from ..services.admin.statsService import StatsService
    
    stats = StatsService.get_dashboard_stats()
    user_sessions = StatsService.get_user_sessions_preview()
    
    return render_template('admin/dashboard.html', 
                         user=current_user,
                         stats=stats,
                         user_sessions=user_sessions)


@admin_bp.route('/assessments')
@login_required
@admin_required
@raw_response
def assessments():
    """Admin assessments management"""
    return render_template('admin/assessments.html', user=current_user)


@admin_bp.route('/logs')
@login_required
@admin_required
@raw_response
def logs():
    """Admin system logs"""
    return render_template('admin/logs.html', user=current_user)


@admin_bp.route('/media')
@login_required
@admin_required
@raw_response
def media():
    """Admin media management"""
    return render_template('admin/media.html', user=current_user)


@admin_bp.route('/settings')
@login_required
@admin_required
@raw_response
def settings():
    """Admin settings page"""
    return render_template('admin/settings.html', user=current_user)


@admin_bp.route('/settings/phq')
@login_required
@admin_required
@raw_response
def phq_settings():
    """PHQ Assessment Settings"""
    return render_template('admin/settings/phq/index.html', user=current_user)


@admin_bp.route('/settings/llm')
@login_required
@admin_required
@raw_response
def llm_settings():
    """LLM Settings Page"""
    return render_template('admin/settings/llm/index.html', user=current_user)



@admin_bp.route('/settings/camera')
@login_required
@admin_required
@raw_response
def camera_settings():
    """Camera Settings"""
    return render_template('admin/settings/camera/index.html', user=current_user)


@admin_bp.route('/settings/consent')
@login_required
@admin_required
@raw_response
def consent_settings():
    """Consent Settings"""
    return render_template('admin/settings/consent/index.html', user=current_user)


@admin_bp.route('/phq')
@login_required
@admin_required
@raw_response
def phq():
    """PHQ Assessment Settings (direct access)"""
    from ..services.admin.phqService import PHQService
    
    # Fetch all PHQ data server-side
    try:
        # Get settings, scales, and categories
        settings_list = PHQService.get_settings()
        scales_list = PHQService.get_scales()
        categories_list = PHQService.get_categories()
        
        # Get questions for each category
        questions_by_category = {}
        for category in categories_list:
            questions = PHQService.get_questions(category['name_id'])
            questions_by_category[category['name_id']] = [q['question_text_id'] for q in questions]
        
        # Find default or first entries
        default_settings = next((s for s in settings_list if s['is_default']), settings_list[0] if settings_list else None)
        default_scale = next((s for s in scales_list if s['is_default']), scales_list[0] if scales_list else None)
        
        phq_data = {
            'settings': default_settings,
            'scale': default_scale,
            'categories': categories_list,
            'questions_by_category': questions_by_category
        }
        
    except Exception as e:
        # Fallback to empty data if there's an error
        phq_data = {
            'settings': None,
            'scale': None,
            'categories': [],
            'questions_by_category': {}
        }
    
    return render_template('admin/settings/phq/index.html', 
                         user=current_user, 
                         phq_data=phq_data)