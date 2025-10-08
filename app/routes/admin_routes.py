# app/routes/admin_routes.py
from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import current_user, login_required
from ..decorators import raw_response, admin_required, api_response

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/')
@login_required
@admin_required
@raw_response
def dashboard():
    """Admin dashboard with pagination and search"""
    from flask import request
    from ..services.admin.statsService import StatsService

    # Get pagination, search, and sort parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)  # Default 15 per page
    search_query = request.args.get('q', '').strip()  # Search query
    sort_by = request.args.get('sort_by', 'user_id')  # Sort field
    sort_order = request.args.get('sort_order', 'asc')  # Sort order

    # Limit per_page options
    if per_page not in [10, 15, 20]:
        per_page = 15

    # Validate sort_by options
    if sort_by not in ['user_id', 'username', 'created_at']:
        sort_by = 'user_id'

    # Validate sort_order options
    if sort_order not in ['asc', 'desc']:
        sort_order = 'asc'

    stats = StatsService.get_dashboard_stats()
    user_sessions_page = StatsService.get_user_sessions_preview(
        page=page,
        per_page=per_page,
        search_query=search_query,
        sort_by=sort_by,
        sort_order=sort_order
    )
    phq_stats = StatsService.get_phq_statistics()
    session_stats = StatsService.get_session_statistics()
    user_stats = StatsService.get_user_statistics()

    return render_template('admin/dashboard.html',
                         user=current_user,
                         stats=stats,
                         user_sessions_page=user_sessions_page,
                         phq_stats=phq_stats,
                         session_stats=session_stats,
                         user_stats=user_stats,
                         search_query=search_query,
                         sort_by=sort_by,
                         sort_order=sort_order)

@admin_bp.route('/ajax-data')
@login_required
@admin_required
@api_response
def dashboard_ajax_data():
    """AJAX endpoint for both pagination and search - returns same data structure"""
    from flask import request
    from ..services.admin.statsService import StatsService

    # Get pagination, search, and sort parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    search_query = request.args.get('q', '').strip()
    sort_by = request.args.get('sort_by', 'user_id')
    sort_order = request.args.get('sort_order', 'asc')

    # Limit per_page options
    if per_page not in [10, 15, 20]:
        per_page = 15

    # Validate sort_by options
    if sort_by not in ['user_id', 'username', 'created_at']:
        sort_by = 'user_id'

    # Validate sort_order options
    if sort_order not in ['asc', 'desc']:
        sort_order = 'asc'

    # Get paginated results (works for both search and regular pagination)
    user_sessions_page = StatsService.get_user_sessions_preview(
        page=page,
        per_page=per_page,
        search_query=search_query,
        sort_by=sort_by,
        sort_order=sort_order
    )

    # Return JSON response in same format as search endpoint
    return {
        'status': 'success',
        'data': {
            'items': user_sessions_page.items,
            'pagination': {
                'page': user_sessions_page.page,
                'pages': user_sessions_page.pages,
                'per_page': user_sessions_page.per_page,
                'total': user_sessions_page.total,
                'has_prev': user_sessions_page.has_prev,
                'has_next': user_sessions_page.has_next,
                'prev_num': user_sessions_page.prev_num,
                'next_num': user_sessions_page.next_num
            },
            'search_query': search_query,
            'sort_by': sort_by,
            'sort_order': sort_order
        }
    }


@admin_bp.route('/search-users')
@login_required
@admin_required
@api_response
def search_users_ajax():
    """AJAX endpoint for searching users with pagination"""
    from flask import request
    from ..services.admin.statsService import StatsService

    # Get pagination, search, and sort parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    search_query = request.args.get('q', '').strip()
    sort_by = request.args.get('sort_by', 'user_id')
    sort_order = request.args.get('sort_order', 'asc')

    # Limit per_page options
    if per_page not in [10, 15, 20]:
        per_page = 15

    # Validate sort_by options
    if sort_by not in ['user_id', 'username', 'created_at']:
        sort_by = 'user_id'

    # Validate sort_order options
    if sort_order not in ['asc', 'desc']:
        sort_order = 'asc'

    # Get paginated search results
    user_sessions_page = StatsService.get_user_sessions_preview(
        page=page,
        per_page=per_page,
        search_query=search_query,
        sort_by=sort_by,
        sort_order=sort_order
    )

    # Return JSON response for AJAX
    return {
        'status': 'success',
        'data': {
            'items': user_sessions_page.items,
            'pagination': {
                'page': user_sessions_page.page,
                'pages': user_sessions_page.pages,
                'per_page': user_sessions_page.per_page,
                'total': user_sessions_page.total,
                'has_prev': user_sessions_page.has_prev,
                'has_next': user_sessions_page.has_next,
                'prev_num': user_sessions_page.prev_num,
                'next_num': user_sessions_page.next_num
            },
            'search_query': search_query,
            'sort_by': sort_by,
            'sort_order': sort_order
        }
    }



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