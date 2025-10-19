# app/routes/admin_routes.py
from flask import Blueprint, render_template
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

    return render_template('admin/dashboard/index.html',
                         user=current_user,
                         stats=stats,
                         user_sessions_page=user_sessions_page,
                         phq_stats=phq_stats,
                         session_stats=session_stats,
                         user_stats=user_stats,
                         search_query=search_query,
                         sort_by=sort_by,
                         sort_order=sort_order)

@admin_bp.route('/ajax-dashboard-data')
@login_required
@admin_required
@api_response
def dashboard_ajax_data():
    """AJAX endpoint for dashboard data - supports multiple tabs

    Parameters:
        tab: 'user-sessions' (default), 'facial-analysis', or 'session-exports'
        page: Page number (default 1)
        per_page: Items per page (default 15)
        q: Search query
        sort_by: Sort field
        sort_order: Sort direction (asc/desc)
    """
    from flask import request
    from ..services.admin.statsService import StatsService
    from ..model.assessment.facial_analysis import SessionFacialAnalysis

    # Get pagination, search, and sort parameters
    tab = request.args.get('tab', 'user-sessions').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    search_query = request.args.get('q', '').strip()
    sort_by = request.args.get('sort_by', 'user_id')
    sort_order = request.args.get('sort_order', 'asc')

    # Limit per_page options
    if per_page not in [10, 15, 20]:
        per_page = 15

    # Validate sort_by options
    if sort_by not in ['user_id', 'username', 'created_at', 'session_number']:
        sort_by = 'user_id'

    # Validate sort_order options
    if sort_order not in ['asc', 'desc']:
        sort_order = 'asc'

    # Validate tab parameter (accept both 'session-exports' and 'facial-analysis-exports')
    if tab == 'facial-analysis-exports':
        tab = 'session-exports'  # Normalize to backend name
    elif tab not in ['user-sessions', 'facial-analysis', 'session-exports']:
        tab = 'user-sessions'

    # Get user sessions data (used by all tabs)
    user_sessions_page = StatsService.get_user_sessions_preview(
        page=page,
        per_page=per_page,
        search_query=search_query,
        sort_by=sort_by,
        sort_order=sort_order
    )

    # Build response based on tab
    response_data = {
        'status': 'success',
        'tab': tab,
        'user_sessions': {
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
            }
        },
        'search_query': search_query,
        'sort_by': sort_by,
        'sort_order': sort_order
    }

    # Add tab-specific data
    if tab == 'user-sessions':
        # Original dashboard view - include all stats
        response_data['stats'] = StatsService.get_dashboard_stats()
        response_data['phq_stats'] = StatsService.get_phq_statistics()
        response_data['session_stats'] = StatsService.get_session_statistics()
        response_data['user_stats'] = StatsService.get_user_statistics()

    elif tab == 'facial-analysis':
        # Facial analysis tab - add facial analysis data to each session
        from ..db import get_session
        from ..model.assessment.sessions import CameraCapture, PHQResponse, LLMConversation
        from sqlalchemy import func

        with get_session() as db:
            # Add facial analysis status to each session item
            for item in response_data['user_sessions']['items']:
                session1_id = item.get('session1_id')
                session2_id = item.get('session2_id')

                # Get facial analysis for session 1
                if session1_id:
                    phq_analysis = db.query(SessionFacialAnalysis).filter_by(
                        session_id=session1_id,
                        assessment_type='PHQ'
                    ).first()
                    llm_analysis = db.query(SessionFacialAnalysis).filter_by(
                        session_id=session1_id,
                        assessment_type='LLM'
                    ).first()

                    phq_images = db.query(func.count(CameraCapture.id)).filter_by(
                        session_id=session1_id
                    ).scalar() or 0
                    llm_images = db.query(func.count(CameraCapture.id)).filter_by(
                        session_id=session1_id
                    ).scalar() or 0

                    item['session1_facial_analysis'] = {
                        'phq_status': phq_analysis.status if phq_analysis else 'not_started',
                        'llm_status': llm_analysis.status if llm_analysis else 'not_started',
                        'phq_images': phq_images,
                        'llm_images': llm_images
                    }

                # Get facial analysis for session 2
                if session2_id:
                    phq_analysis = db.query(SessionFacialAnalysis).filter_by(
                        session_id=session2_id,
                        assessment_type='PHQ'
                    ).first()
                    llm_analysis = db.query(SessionFacialAnalysis).filter_by(
                        session_id=session2_id,
                        assessment_type='LLM'
                    ).first()

                    phq_images = db.query(func.count(CameraCapture.id)).filter_by(
                        session_id=session2_id
                    ).scalar() or 0
                    llm_images = db.query(func.count(CameraCapture.id)).filter_by(
                        session_id=session2_id
                    ).scalar() or 0

                    item['session2_facial_analysis'] = {
                        'phq_status': phq_analysis.status if phq_analysis else 'not_started',
                        'llm_status': llm_analysis.status if llm_analysis else 'not_started',
                        'phq_images': phq_images,
                        'llm_images': llm_images
                    }

    elif tab == 'session-exports':
        # Session exports tab - add facial analysis status and download flag
        from ..db import get_session

        with get_session() as db:
            # Add facial analysis status to each session item
            for item in response_data['user_sessions']['items']:
                session1_id = item.get('session1_id')
                session2_id = item.get('session2_id')

                # Get facial analysis for session 1
                if session1_id:
                    phq_analysis = db.query(SessionFacialAnalysis).filter_by(
                        session_id=session1_id,
                        assessment_type='PHQ'
                    ).first()
                    llm_analysis = db.query(SessionFacialAnalysis).filter_by(
                        session_id=session1_id,
                        assessment_type='LLM'
                    ).first()

                    phq_status = phq_analysis.status if phq_analysis else 'not_started'
                    llm_status = llm_analysis.status if llm_analysis else 'not_started'
                    both_completed = (phq_status == 'completed' and llm_status == 'completed')

                    item['session1_facial_analysis'] = {
                        'phq_status': phq_status,
                        'llm_status': llm_status,
                        'can_download': both_completed
                    }

                # Get facial analysis for session 2
                if session2_id:
                    phq_analysis = db.query(SessionFacialAnalysis).filter_by(
                        session_id=session2_id,
                        assessment_type='PHQ'
                    ).first()
                    llm_analysis = db.query(SessionFacialAnalysis).filter_by(
                        session_id=session2_id,
                        assessment_type='LLM'
                    ).first()

                    phq_status = phq_analysis.status if phq_analysis else 'not_started'
                    llm_status = llm_analysis.status if llm_analysis else 'not_started'
                    both_completed = (phq_status == 'completed' and llm_status == 'completed')

                    item['session2_facial_analysis'] = {
                        'phq_status': phq_status,
                        'llm_status': llm_status,
                        'can_download': both_completed
                    }

    return {
        'status': 'success',
        'data': response_data
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