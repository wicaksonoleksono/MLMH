from ...db import get_session
from ...model.shared.users import User
from ...model.shared.enums import UserType
from ...model.assessment.sessions import AssessmentSession, PHQResponse
from sqlalchemy import func

class StatsService:
    @staticmethod
    def get_dashboard_stats():
        """Get basic stats for admin dashboard"""
        try:
            with get_session() as db:
                # User stats
                total_users = db.query(User).count()
                admin_users = db.query(User).join(UserType).filter(UserType.name == 'admin').count()
                regular_users = total_users - admin_users
                
                # Session stats
                total_sessions = db.query(AssessmentSession).count()
                completed_sessions = db.query(AssessmentSession).filter(AssessmentSession.status == 'COMPLETED').count()
                completion_rate = int((completed_sessions / total_sessions * 100)) if total_sessions > 0 else 0
                
                return {
                    'users': {
                        'total': total_users,
                        'admins': admin_users,
                        'regular': regular_users
                    },
                    'assessments': {
                        'total_sessions': total_sessions,
                        'completed_sessions': completed_sessions,
                        'completion_rate': completion_rate
                    },
                    'settings': {
                        'total_settings': 4,
                        'assessment_configs': 2,
                        'media_settings': 1
                    }
                }
        except Exception as e:
            # Return default values if there's an error
            return {
                'users': {
                    'total': 0,
                    'admins': 0,
                    'regular': 0
                },
                'assessments': {
                    'total_sessions': 0,
                    'completed_sessions': 0,
                    'completion_rate': 0
                },
                'settings': {
                    'total_settings': 0,
                    'assessment_configs': 0,
                    'media_settings': 0
                }
            }
    
    @staticmethod
    def get_user_sessions_preview(page=1, per_page=20, search_query=None):
        """Get paginated user sessions preview: UserID | Username | Session1 | Session2 | PHQ-Sum"""
        try:
            with get_session() as db:
                # Build base query with JOINs to avoid N+1 queries
                from sqlalchemy.orm import joinedload
                from sqlalchemy import func, and_
                
                # Base query with user type filter
                base_query = db.query(User).join(UserType).filter(UserType.name == 'user')
                
                # Add search filter if query provided
                if search_query:
                    base_query = base_query.filter(User.uname.ilike(f'%{search_query}%'))
                
                # Order by user ID for consistent pagination
                base_query = base_query.order_by(User.id)
                
                # Get total count for pagination
                total_users = base_query.count()
                
                # Apply pagination
                offset = (page - 1) * per_page
                users_on_page = base_query.offset(offset).limit(per_page).all()
                
                # Pre-fetch all related data in bulk to avoid N+1 queries
                user_ids = [user.id for user in users_on_page]
                if user_ids:
                    # Get all sessions for these users in one query
                    all_sessions = db.query(AssessmentSession).filter(
                        AssessmentSession.user_id.in_(user_ids)
                    ).order_by(AssessmentSession.user_id, AssessmentSession.created_at).all()
                    
                    # Group sessions by user_id for easier access
                    sessions_by_user = {}
                    for session in all_sessions:
                        if session.user_id not in sessions_by_user:
                            sessions_by_user[session.user_id] = []
                        sessions_by_user[session.user_id].append(session)
                    
                    # Get all PHQ responses for these sessions in one query
                    session_ids = [session.id for session in all_sessions]
                    all_phq_responses = {}
                    if session_ids:
                        phq_responses = db.query(PHQResponse).filter(
                            PHQResponse.session_id.in_(session_ids)
                        ).all()
                        all_phq_responses = {resp.session_id: resp for resp in phq_responses}
                else:
                    sessions_by_user = {}
                    all_phq_responses = {}
                
                # Process data for preview
                preview_data = []
                for user in users_on_page:
                    # Get user's sessions from pre-fetched data
                    user_sessions = sessions_by_user.get(user.id, [])
                    
                    # Get PHQ scores for each session using pre-fetched data
                    session1_phq_score = None
                    session2_phq_score = None
                    
                    if len(user_sessions) >= 1:
                        session1_response_record = all_phq_responses.get(user_sessions[0].id)
                        if session1_response_record and session1_response_record.responses:
                            session1_phq_score = sum(
                                response_data.get('response_value', 0) 
                                for response_data in session1_response_record.responses.values()
                            )
                    
                    if len(user_sessions) >= 2:
                        session2_response_record = all_phq_responses.get(user_sessions[1].id)
                        if session2_response_record and session2_response_record.responses:
                            session2_phq_score = sum(
                                response_data.get('response_value', 0) 
                                for response_data in session2_response_record.responses.values()
                            )
                
                    # Just rawdog the backend status values
                    session1_status = user_sessions[0].status if len(user_sessions) >= 1 else "Not done"
                    session2_status = user_sessions[1].status if len(user_sessions) >= 2 else "Not done"

                    preview_data.append({
                        'user_id': user.id,
                        'username': user.uname,
                        'session1': session1_status,
                        'session2': session2_status,
                        'session1_phq_score': session1_phq_score,
                        'session2_phq_score': session2_phq_score,
                        'session1_id': user_sessions[0].id if len(user_sessions) >= 1 else None,
                        'session2_id': user_sessions[1].id if len(user_sessions) >= 2 else None
                    })
                
                # Calculate pagination info
                has_prev = page > 1
                has_next = offset + per_page < total_users
                pages = (total_users + per_page - 1) // per_page  # Ceiling division
                prev_num = page - 1 if has_prev else None
                next_num = page + 1 if has_next else None
                
                # Create pagination object manually
                from collections import namedtuple
                PageObj = namedtuple('PageObj', ['items', 'page', 'pages', 'per_page', 'total', 'has_prev', 'has_next', 'prev_num', 'next_num'])
                page_obj = PageObj(
                    items=preview_data,
                    page=page,
                    pages=pages,
                    per_page=per_page,
                    total=total_users,
                    has_prev=has_prev,
                    has_next=has_next,
                    prev_num=prev_num,
                    next_num=next_num
                )
                
                return page_obj
        except Exception as e:
            # Log the error and return empty pagination object
            print(f"[ERROR] StatsService.get_user_sessions_preview failed: {str(e)}")
            import traceback
            traceback.print_exc()
            from collections import namedtuple
            EmptyPage = namedtuple('EmptyPage', ['items', 'page', 'pages', 'per_page', 'total', 'has_prev', 'has_next', 'prev_num', 'next_num'])
            return EmptyPage([], 1, 0, per_page, 0, False, False, None, None)
    
    @staticmethod
    def get_all_user_sessions_for_export():
        """Get ALL user sessions for bulk export (no pagination)"""
        try:
            with get_session() as db:
                # Get regular users only
                users = db.query(User).join(UserType).filter(UserType.name == 'user').all()
                
                completed_users = []  # Both sessions completed
                incomplete_users = []  # Only session 1 completed
                
                for user in users:
                    # Get user's sessions
                    sessions = db.query(AssessmentSession).filter(
                        AssessmentSession.user_id == user.id
                    ).order_by(AssessmentSession.created_at).all()
                    
                    # Check completion status
                    session1_complete = len(sessions) >= 1 and sessions[0].status == 'COMPLETED'
                    session2_complete = len(sessions) >= 2 and sessions[1].status == 'COMPLETED'
                    
                    if session1_complete and session2_complete:
                        completed_users.append({
                            'user': user,
                            'sessions': sessions,
                            'type': 'completed'
                        })
                    elif session1_complete:
                        incomplete_users.append({
                            'user': user,
                            'sessions': sessions,
                            'type': 'incomplete'
                        })
                
                return {
                    'completed': completed_users,
                    'incomplete': incomplete_users,
                    'total_completed': len(completed_users),
                    'total_incomplete': len(incomplete_users)
                }
        except Exception as e:
            return {
                'completed': [],
                'incomplete': [],
                'total_completed': 0,
                'total_incomplete': 0
            }
    
    @staticmethod
    def get_phq_statistics():
        """Get PHQ-9 score distribution statistics"""
        try:
            with get_session() as db:
                # Get all completed sessions with PHQ responses
                completed_sessions = db.query(AssessmentSession).filter(
                    AssessmentSession.status == 'COMPLETED'
                ).all()
                
                # Calculate PHQ scores for each session using new JSON structure
                phq_scores = []
                for session in completed_sessions:
                    response_record = db.query(PHQResponse).filter(
                        PHQResponse.session_id == session.id
                    ).first()
                    if response_record and response_record.responses:
                        score = sum(
                            response_data.get('response_value', 0) 
                            for response_data in response_record.responses.values()
                        )
                        phq_scores.append(score)
                
                # Categorize scores according to PHQ-9 severity levels
                minimal = len([score for score in phq_scores if 0 <= score <= 4])
                mild = len([score for score in phq_scores if 5 <= score <= 9])
                moderate = len([score for score in phq_scores if 10 <= score <= 14])
                moderate_severe = len([score for score in phq_scores if 15 <= score <= 19])
                severe = len([score for score in phq_scores if 20 <= score <= 27])
                
                return {
                    'minimal': minimal,
                    'mild': mild,
                    'moderate': moderate,
                    'moderate_severe': moderate_severe,
                    'severe': severe,
                    'total_scores': len(phq_scores),
                    'average_score': round(sum(phq_scores) / len(phq_scores), 2) if phq_scores else 0
                }
        except Exception as e:
            # Return default values if there's an error
            return {
                'minimal': 0,
                'mild': 0,
                'moderate': 0,
                'moderate_severe': 0,
                'severe': 0,
                'total_scores': 0,
                'average_score': 0
            }
    
    @staticmethod
    def get_session_statistics():
        """Get session completion statistics"""
        try:
            with get_session() as db:
                # Count users by number of sessions
                user_session_counts = db.query(
                    User.id,
                    func.count(AssessmentSession.id).label('session_count')
                ).outerjoin(AssessmentSession).group_by(User.id).all()
                
                # Count users with only session 1, both sessions, etc.
                session1_only = len([u for u in user_session_counts if u.session_count == 1])
                both_sessions = len([u for u in user_session_counts if u.session_count >= 2])
                
                return {
                    'session1_only': session1_only,
                    'both_sessions': both_sessions
                }
        except Exception as e:
            # Return default values if there's an error
            return {
                'session1_only': 0,
                'both_sessions': 0
            }
    
    @staticmethod
    def get_user_statistics():
        """Get user engagement statistics"""
        try:
            with get_session() as db:
                # Total users
                total_users = db.query(User).join(UserType).filter(UserType.name == 'user').count()
                
                # Active users (users with at least one session)
                active_users = db.query(User).join(UserType).join(AssessmentSession).filter(
                    UserType.name == 'user'
                ).distinct().count()
                
                # Average sessions per user
                total_sessions = db.query(AssessmentSession).count()
                avg_sessions_per_user = round(total_sessions / total_users, 2) if total_users > 0 else 0
                
                # High engagement (users with 2+ sessions)
                high_engagement_users = db.query(
                    User.id
                ).join(AssessmentSession).group_by(User.id).having(
                    func.count(AssessmentSession.id) >= 2
                ).count()
                
                # Low engagement (users with 0 sessions)
                low_engagement_users = db.query(User).join(UserType).filter(
                    UserType.name == 'user'
                ).outerjoin(AssessmentSession).filter(
                    AssessmentSession.id.is_(None)
                ).count()
                
                return {
                    'active_users': active_users,
                    'avg_sessions_per_user': avg_sessions_per_user,
                    'high_engagement': high_engagement_users,
                    'low_engagement': low_engagement_users
                }
        except Exception as e:
            # Return default values if there's an error
            return {
                'active_users': 0,
                'avg_sessions_per_user': 0,
                'high_engagement': 0,
                'low_engagement': 0
            }