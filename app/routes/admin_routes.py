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
        # Facial analysis tab - query ALL completed sessions directly from database
        # Don't rely on paginated user list - query sessions directly
        from ..db import get_session
        from ..model.assessment.sessions import CameraCapture, AssessmentSession
        from ..model.shared.users import User
        from sqlalchemy import func, and_

        with get_session() as db:
            # Get the LATEST session for each (user_id, session_number) pair where status is COMPLETED
            # This ensures we show only the most recent attempt, not old/reset sessions
            subquery = db.query(
                AssessmentSession.user_id,
                AssessmentSession.session_number,
                func.max(AssessmentSession.created_at).label('latest_created_at')
            ).filter(
                AssessmentSession.status == 'COMPLETED'  # Only COMPLETED sessions
            ).group_by(
                AssessmentSession.user_id,
                AssessmentSession.session_number
            ).subquery()

            # Get all completed sessions (latest for each user+session_number)
            completed_sessions = db.query(AssessmentSession).join(
                subquery,
                and_(
                    AssessmentSession.user_id == subquery.c.user_id,
                    AssessmentSession.session_number == subquery.c.session_number,
                    AssessmentSession.created_at == subquery.c.latest_created_at
                )
            ).join(User).order_by(User.id, AssessmentSession.session_number).all()

            # Group sessions by user_id
            sessions_by_user = {}
            for session in completed_sessions:
                if session.user_id not in sessions_by_user:
                    sessions_by_user[session.user_id] = {}
                sessions_by_user[session.user_id][session.session_number] = session

            # Build user items from completed sessions
            facial_analysis_items = []
            processed_users = set()

            for session in completed_sessions:
                if session.user_id in processed_users:
                    continue
                processed_users.add(session.user_id)

                user_sessions = sessions_by_user[session.user_id]
                session1_obj = user_sessions.get(1)
                session2_obj = user_sessions.get(2)

                item = {
                    'user_id': session.user_id,
                    'username': session.user.uname,
                    'email': session.user.email or '',
                    'session1': session1_obj.status if session1_obj else 'Not done',
                    'session1_id': session1_obj.id if session1_obj else None,
                    'session2': session2_obj.status if session2_obj else 'Not done',
                    'session2_id': session2_obj.id if session2_obj else None
                }

                # Add facial analysis data for Session 1 (always exists if we're here)
                if session1_obj:
                    phq_analysis = db.query(SessionFacialAnalysis).filter_by(
                        session_id=session1_obj.id,
                        assessment_type='PHQ'
                    ).first()
                    llm_analysis = db.query(SessionFacialAnalysis).filter_by(
                        session_id=session1_obj.id,
                        assessment_type='LLM'
                    ).first()

                    # Count actual images for PHQ and LLM
                    phq_captures = db.query(CameraCapture).filter_by(
                        session_id=session1_obj.id,
                        capture_type='PHQ'
                    ).all()
                    phq_images = sum(len(capture.filenames) for capture in phq_captures)

                    llm_captures = db.query(CameraCapture).filter_by(
                        session_id=session1_obj.id,
                        capture_type='LLM'
                    ).all()
                    llm_images = sum(len(capture.filenames) for capture in llm_captures)

                    item['session1_facial_analysis'] = {
                        'phq_status': phq_analysis.status if phq_analysis else 'not_started',
                        'llm_status': llm_analysis.status if llm_analysis else 'not_started',
                        'phq_images': phq_images,
                        'llm_images': llm_images
                    }

                # Add facial analysis data for Session 2 (if exists and COMPLETED)
                if session2_obj:
                    phq_analysis = db.query(SessionFacialAnalysis).filter_by(
                        session_id=session2_obj.id,
                        assessment_type='PHQ'
                    ).first()
                    llm_analysis = db.query(SessionFacialAnalysis).filter_by(
                        session_id=session2_obj.id,
                        assessment_type='LLM'
                    ).first()

                    # Count actual images for PHQ and LLM
                    phq_captures = db.query(CameraCapture).filter_by(
                        session_id=session2_obj.id,
                        capture_type='PHQ'
                    ).all()
                    phq_images = sum(len(capture.filenames) for capture in phq_captures)

                    llm_captures = db.query(CameraCapture).filter_by(
                        session_id=session2_obj.id,
                        capture_type='LLM'
                    ).all()
                    llm_images = sum(len(capture.filenames) for capture in llm_captures)

                    item['session2_facial_analysis'] = {
                        'phq_status': phq_analysis.status if phq_analysis else 'not_started',
                        'llm_status': llm_analysis.status if llm_analysis else 'not_started',
                        'phq_images': phq_images,
                        'llm_images': llm_images
                    }

                facial_analysis_items.append(item)

            # Apply search filter if provided
            if search_query:
                facial_analysis_items = [
                    item for item in facial_analysis_items
                    if search_query.lower() in item['username'].lower() or
                       search_query.lower() in item.get('email', '').lower()
                ]

            # Apply pagination to filtered results
            total_items = len(facial_analysis_items)
            offset = (page - 1) * per_page
            paginated_items = facial_analysis_items[offset:offset + per_page]

            # Calculate pagination info
            has_prev = page > 1
            has_next = offset + per_page < total_items
            pages = (total_items + per_page - 1) // per_page if total_items > 0 else 0
            prev_num = page - 1 if has_prev else None
            next_num = page + 1 if has_next else None

            # Replace the items with our custom query results
            response_data['user_sessions'] = {
                'items': paginated_items,
                'pagination': {
                    'page': page,
                    'pages': pages,
                    'per_page': per_page,
                    'total': total_items,
                    'has_prev': has_prev,
                    'has_next': has_next,
                    'prev_num': prev_num,
                    'next_num': next_num
                }
            }

    elif tab == 'session-exports':
        # Session exports tab - query ALL completed sessions directly, filter by facial analysis completion
        from ..db import get_session
        from ..model.assessment.sessions import AssessmentSession
        from ..model.shared.users import User
        from sqlalchemy import func, and_

        with get_session() as db:
            # Step 1: Get ALL COMPLETED sessions (latest for each user+session_number)
            subquery = db.query(
                AssessmentSession.user_id,
                AssessmentSession.session_number,
                func.max(AssessmentSession.created_at).label('latest_created_at')
            ).filter(
                AssessmentSession.status == 'COMPLETED'
            ).group_by(
                AssessmentSession.user_id,
                AssessmentSession.session_number
            ).subquery()

            completed_sessions = db.query(AssessmentSession).join(
                subquery,
                and_(
                    AssessmentSession.user_id == subquery.c.user_id,
                    AssessmentSession.session_number == subquery.c.session_number,
                    AssessmentSession.created_at == subquery.c.latest_created_at
                )
            ).join(User).order_by(User.id, AssessmentSession.session_number).all()

            # Step 2: Get facial analysis for all sessions in one query
            session_ids = [s.id for s in completed_sessions]
            facial_analysis_map = {}
            if session_ids:
                analyses = db.query(SessionFacialAnalysis).filter(
                    SessionFacialAnalysis.session_id.in_(session_ids)
                ).all()
                for analysis in analyses:
                    if analysis.session_id not in facial_analysis_map:
                        facial_analysis_map[analysis.session_id] = {}
                    facial_analysis_map[analysis.session_id][analysis.assessment_type] = analysis

            # Step 3: Build flat list of individual sessions with facial analysis data
            # ONLY include sessions where BOTH PHQ and LLM are completed
            all_sessions = []
            for session in completed_sessions:
                analyses = facial_analysis_map.get(session.id, {})
                phq_analysis = analyses.get('PHQ')
                llm_analysis = analyses.get('LLM')

                phq_status = phq_analysis.status if phq_analysis else 'not_started'
                llm_status = llm_analysis.status if llm_analysis else 'not_started'

                # CONSTRAINT: Only include if BOTH are completed
                if phq_status == 'completed' and llm_status == 'completed':
                    all_sessions.append({
                        'id': session.id,
                        'user_id': session.user_id,
                        'username': session.user.uname,
                        'session_number': session.session_number,
                        'phq_status': phq_status,
                        'llm_status': llm_status,
                        'can_download': True  # Always true if we reach here
                    })

            # Step 4: Apply search filter if provided
            if search_query:
                all_sessions = [
                    s for s in all_sessions
                    if search_query.lower() in s['username'].lower()
                ]

            # Step 5: Paginate filtered sessions
            total_sessions = len(all_sessions)
            offset = (page - 1) * per_page
            paginated_sessions = all_sessions[offset:offset + per_page]

            # Calculate pagination info
            has_prev = page > 1
            has_next = offset + per_page < total_sessions
            pages = (total_sessions + per_page - 1) // per_page if total_sessions > 0 else 0
            prev_num = page - 1 if has_prev else None
            next_num = page + 1 if has_next else None

            # Step 6: Replace response data with session-level pagination
            response_data['user_sessions'] = {
                'items': paginated_sessions,
                'pagination': {
                    'page': page,
                    'pages': pages,
                    'per_page': per_page,
                    'total': total_sessions,
                    'has_prev': has_prev,
                    'has_next': has_next,
                    'prev_num': prev_num,
                    'next_num': next_num
                }
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